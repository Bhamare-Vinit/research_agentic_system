import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agent import llm, tokens
from agent.prompts import render_prompt
from agent.settings import MAIN_AGENT_MAX_STEPS, MAX_RESEARCH_ITERATIONS
from agent.tools import dossier_tools, storage

BLOCK_TYPES = ("summary", "findings", "sources", "gap", "update")
PROSE_BLOCKS = ("summary", "gap")
HISTORY_TURNS = 8


class RetrieveInput(BaseModel):
    topic: str = Field(description="the topic key exactly as check_memory showed it")
    information: str = Field(description="the information category within that topic")


class ResearchInput(BaseModel):
    topic: str = Field(description="the topic key this research belongs under")
    information: str = Field(description="the information category this research belongs under")
    research_question: str = Field(
        description="the specific question the Research Agent should answer from live sources"
    )


class AnswerBlock(BaseModel):
    type: str = Field(description="one of summary, findings, sources, gap, update")
    text: str = Field(default="", description="prose for summary, gap and update blocks")
    finding_ids: list[str] = Field(
        default_factory=list, description="ids copied exactly from retrieve, never invented"
    )


class AnswerInput(BaseModel):
    blocks: list[AnswerBlock] = Field(description="the blocks this particular reply needs")


def as_block(block):
    if isinstance(block, AnswerBlock):
        return block.model_dump()
    if isinstance(block, dict):
        return block
    return {}


def format_history(messages):
    recent = messages[-HISTORY_TURNS:]
    if not recent:
        return "(this is the first message of the session)"
    lines = []
    for message in recent:
        speaker = "user" if getattr(message, "type", "") == "human" else "dossier"
        lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)


def hydrate_blocks(specs, available):
    by_id = {finding["id"]: finding for finding in available}
    by_source = {finding["source"]: finding for finding in available}
    blocks = []
    dropped = []

    for spec in specs:
        block = as_block(spec)
        if block.get("type") not in BLOCK_TYPES:
            continue

        resolved = []
        for reference in block.get("finding_ids") or []:
            finding = by_id.get(reference) or by_source.get(reference)
            if finding is None:
                dropped.append(reference)
            elif finding not in resolved:
                resolved.append(finding)

        text = (block.get("text") or "").strip()
        if not text and not resolved:
            continue

        blocks.append({"type": block["type"], "text": text or None, "findings": resolved})

    return blocks, dropped


def fill_source_blocks(blocks):
    cited = []
    seen = set()
    for block in blocks:
        for finding in block["findings"]:
            if finding["id"] not in seen:
                seen.add(finding["id"])
                cited.append(finding)

    for block in blocks:
        if block["type"] != "sources":
            continue
        block["text"] = None
        if not block["findings"]:
            block["findings"] = list(cited)

    return [block for block in blocks if block["type"] != "sources" or block["findings"]]


def build_toolkit(seen_findings, activity, outcome, iteration):
    def record(tool_name, summary, **extra):
        activity.append(
            {"step": len(activity) + 1, "agent": "main", "tool": tool_name, "summary": summary, **extra}
        )

    def run_check_memory():
        structure = dossier_tools.get_dossier_structure()
        if structure:
            record("check_memory", f"checked the case file: {', '.join(structure)}")
        else:
            record("check_memory", "checked the case file, it is empty")
        return structure

    def run_retrieve(topic, information):
        result = dossier_tools.get_dossier(topic, information)
        for finding in result["findings"]:
            seen_findings[finding["id"]] = finding
        record(
            "retrieve",
            f"read {result['returned']} of {result['total_available']} findings from {result['topic']} / {result['information']}",
            topic=result["topic"],
            information=result["information"],
        )
        return result

    def run_research(topic, information, research_question):
        if iteration >= MAX_RESEARCH_ITERATIONS:
            record("research", "research limit reached, answering from what is on file")
            return {
                "status": "refused",
                "reason": f"you have already run {iteration} research passes this turn, which is the limit. Answer with what the case file holds.",
            }
        outcome["research_task"] = {
            "topic": storage.slugify(topic),
            "information": storage.slugify(information),
            "research_question": research_question,
        }
        record("research", f"handed to the Research Agent: {research_question}")
        return {"status": "dispatched", "research_question": research_question}

    def run_answer(blocks):
        outcome["blocks"] = [as_block(block) for block in blocks]
        record("answer", "composed the reply")
        return {"status": "delivered"}

    return {
        "check_memory": StructuredTool.from_function(
            func=run_check_memory,
            name="check_memory",
            description="List every topic in the case file and the information categories each holds, with counts. Returns no findings.",
        ),
        "retrieve": StructuredTool.from_function(
            func=run_retrieve,
            name="retrieve",
            description="Read the findings stored under one topic and one information category.",
            args_schema=RetrieveInput,
        ),
        "research": StructuredTool.from_function(
            func=run_research,
            name="research",
            description="Hand a specific research question to the Research Agent, which searches the live web and writes what it finds into the case file.",
            args_schema=ResearchInput,
        ),
        "answer": StructuredTool.from_function(
            func=run_answer,
            name="answer",
            description="Deliver the reply to the user as a list of blocks, ending the turn.",
            args_schema=AnswerInput,
        ),
    }


def opening_transcript(state):
    prompt = render_prompt(
        "main_agent",
        history=format_history(state.get("messages", [])[:-1]),
        query=state["user_query"],
    )
    return [HumanMessage(prompt)]


def resumed_transcript(state):
    transcript = list(state.get("agent_messages") or [])
    result = state.get("research_result") or {}
    summary = (
        f"The Research Agent finished. It added {result.get('findings_added', 0)} new findings "
        f"to the case file. {result.get('summary', '')}".strip()
    )
    transcript.append(HumanMessage(f"{summary} Check the case file again before you decide."))
    return transcript


def retrieval_stats(available):
    whole = tokens.count_tokens(storage.load_dossier())
    retrieved = tokens.count_tokens(available)
    return {
        "findings_seen": len(available),
        "whole_dossier_tokens": whole,
        "retrieved_tokens": retrieved,
        "tokens_saved_pct": round(100 * (1 - retrieved / whole), 1) if whole else 0.0,
    }


def settle(state, transcript, outcome, activity, seen_findings):
    available = list(seen_findings.values())
    blocks, dropped = hydrate_blocks(outcome.get("blocks") or [], available)
    blocks = fill_source_blocks(blocks)

    if not blocks:
        blocks = [
            {
                "type": "gap",
                "text": "The case file does not hold anything that answers this yet.",
                "findings": [],
            }
        ]

    answer = " ".join(
        block["text"] for block in blocks if block["type"] in PROSE_BLOCKS and block["text"]
    )

    return {
        "agent_messages": transcript,
        "retrieved_findings_cache": available,
        "activity": activity,
        "research_task": None,
        "blocks": blocks,
        "dropped_finding_ids": dropped,
        "final_answer": answer,
        "retrieval_stats": retrieval_stats(available),
        "messages": [AIMessage(answer or "See the findings below.")],
    }


def run_main_agent(state):
    iteration = state.get("iteration", 0)
    resuming = bool(state.get("agent_messages"))
    transcript = resumed_transcript(state) if resuming else opening_transcript(state)

    seen_findings = {
        finding["id"]: finding for finding in state.get("retrieved_findings_cache", [])
    }
    activity = []
    outcome = {}

    toolkit = build_toolkit(seen_findings, activity, outcome, iteration)
    model = llm.get_tool_llm(list(toolkit.values()))

    for _ in range(MAIN_AGENT_MAX_STEPS):
        response = model.invoke(transcript)
        transcript.append(response)

        calls = getattr(response, "tool_calls", None)
        if not calls:
            break

        for call in calls:
            selected = toolkit.get(call["name"])
            if selected is None:
                output = {"error": f"there is no tool called {call['name']}"}
            else:
                output = selected.invoke(call["args"])
            transcript.append(
                ToolMessage(content=json.dumps(output, default=str)[:12000], tool_call_id=call["id"])
            )
            if call["name"] == "research" and outcome.get("research_task"):
                return {
                    "agent_messages": transcript,
                    "retrieved_findings_cache": list(seen_findings.values()),
                    "activity": activity,
                    "research_task": outcome["research_task"],
                    "research_call_id": call["id"],
                }

        if "blocks" in outcome:
            break

    return settle(state, transcript, outcome, activity, seen_findings)


def route_from_main(state):
    return "research" if state.get("research_task") else "done"
