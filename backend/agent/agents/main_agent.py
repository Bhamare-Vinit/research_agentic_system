import json
import re

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import Literal

from agent import llm, tokens
from agent.prompts import render_prompt
from agent.settings import MAIN_AGENT_MAX_STEPS, MAX_RESEARCH_ITERATIONS, RETRIEVAL_TOP_K
from agent.tools import dossier_tools, storage

BLOCK_TYPES = ("summary", "findings", "gap", "update")
PROSE_BLOCKS = ("summary", "gap")
BLOCKS_SHOWING_URLS = ("findings", "update")
HISTORY_TURNS = 8
TOOL_OUTPUT_LIMIT = 30000

GENERIC_CATEGORIES = dossier_tools.GENERIC_CATEGORIES


class RetrieveInput(BaseModel):
    topic: str = Field(description="the topic key exactly as check_memory showed it")
    information: str = Field(description="the information category within that topic")


class ResearchPlanItem(BaseModel):
    information: str = Field(
        description="a snake_case name for the kind of information this entry covers"
    )
    what_to_find: str = Field(
        description="what the Research Agent should establish under this category"
    )


class ResearchInput(BaseModel):
    topic: str = Field(description="the topic key this research belongs under")
    research_question: str = Field(
        description="the overall question the Research Agent should answer from live sources"
    )
    plan: list[ResearchPlanItem] = Field(
        description="the categories this subject calls for, each with what to find in it"
    )


class AnswerBlock(BaseModel):
    type: Literal["summary", "findings", "gap", "update"] = Field(
        description="which kind of block this is"
    )
    text: str = Field(description="prose for summary, gap and update blocks, or empty")
    finding_ids: list[str] = Field(
        description="ids copied exactly from retrieve, never invented, or an empty list"
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


def strip_finding_ids(text, known_ids):
    for finding_id in sorted(known_ids, key=len, reverse=True):
        text = text.replace(finding_id, "")
    text = re.sub(r"[\[(]\s*(?:[,;]\s*)*[\])]", "", text)
    text = re.sub(r"(?:\s*[,;])+\s*(?=[.\n]|$)", "", text)
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


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

        text = strip_finding_ids(block.get("text") or "", by_id)
        if not text and not resolved:
            continue

        blocks.append({"type": block["type"], "text": text or None, "findings": resolved})

    return blocks, dropped


def summary_first(blocks, fallback_text):
    summaries = [block for block in blocks if block["type"] == "summary"]
    others = [block for block in blocks if block["type"] != "summary"]
    if not summaries:
        summaries = [{"type": "summary", "text": fallback_text, "findings": []}]
    return summaries + others


def add_source_block(blocks):
    shown_urls = {
        finding["source"]
        for block in blocks
        if block["type"] in BLOCKS_SHOWING_URLS
        for finding in block["findings"]
    }

    unshown = []
    seen_urls = set(shown_urls)
    for block in blocks:
        for finding in block["findings"]:
            if finding["source"] not in seen_urls:
                seen_urls.add(finding["source"])
                unshown.append(finding)

    if unshown:
        blocks.append({"type": "sources", "text": None, "findings": unshown})
    return blocks


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

    def run_research(topic, research_question, plan):
        steps = [
            item.model_dump() if isinstance(item, ResearchPlanItem) else dict(item)
            for item in plan or []
        ]
        for step in steps:
            step["information"] = storage.slugify(step.get("information"))

        if not steps:
            record("research", "rejected a research request with no plan")
            return {
                "status": "rejected",
                "reason": "give a plan: the categories to cover and what to find in each.",
            }

        useless = [step["information"] for step in steps if step["information"] in GENERIC_CATEGORIES]
        if useless:
            record("research", f"rejected {', '.join(useless)} as categories")
            return {
                "status": "rejected",
                "reason": (
                    f"{', '.join(useless)} name no particular kind of information. Say what you "
                    "actually want to know: architecture, pricing, benchmarks, limitations, "
                    "training_data, release_date, revenue, manufacturers, timeline, use_cases."
                ),
            }

        if iteration >= MAX_RESEARCH_ITERATIONS:
            record("research", "research limit reached, answering from what is on file")
            return {
                "status": "refused",
                "reason": f"you have already run {iteration} research passes this turn, which is the limit. Answer with what the case file holds.",
            }
        outcome["research_task"] = {
            "topic": storage.slugify(topic),
            "research_question": research_question,
            "plan": steps,
        }
        record(
            "research",
            f"handed to the Research Agent: {research_question}",
            plan=[step["information"] for step in steps],
        )
        return {
            "status": "dispatched",
            "research_question": research_question,
            "covering": [step["information"] for step in steps],
        }

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
            description="Read the findings in the one category that answers the question. Retrieve only what the question needs.",
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
        retrieval_cap=RETRIEVAL_TOP_K,
        research_limit=MAX_RESEARCH_ITERATIONS,
    )
    return [HumanMessage(prompt)]


def research_report(result):
    lines = [
        f"The Research Agent filed {result.get('findings_added', 0)} findings."
    ]

    covered = result.get("categories_covered") or []
    created = result.get("categories_created") or []
    missing = result.get("could_not_establish") or []

    if covered:
        lines.append(f"Categories now holding findings: {', '.join(covered)}.")
    if created:
        lines.append(
            f"It opened new categories you did not ask for: {', '.join(created)}. "
            "Retrieve them too if they bear on the question."
        )
    if missing:
        lines.append(f"It could not establish: {', '.join(missing)}.")
    if not result.get("subject_confirmed", True):
        lines.append(
            "It could not confirm the sources were about this subject at all. Tell the user you "
            "could not find it rather than presenting what it did find."
        )
    if result.get("notes"):
        lines.append(f"Its report: {result['notes']}")

    lines.append("Check the case file again with retrieve before you decide anything.")
    return " ".join(lines)


def resumed_transcript(state):
    transcript = list(state.get("agent_messages") or [])
    transcript.append(HumanMessage(research_report(state.get("research_result") or {})))
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

    answer = " ".join(
        block["text"] for block in blocks if block["type"] in PROSE_BLOCKS and block["text"]
    )
    blocks = summary_first(
        blocks, answer or "The case file does not hold anything that answers this yet."
    )
    blocks = add_source_block(blocks)

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
                ToolMessage(
                    content=json.dumps(output, default=str)[:TOOL_OUTPUT_LIMIT],
                    tool_call_id=call["id"],
                )
            )
            if call["name"] == "research" and outcome.get("research_task"):
                return {
                    "agent_messages": transcript,
                    "retrieved_findings_cache": list(seen_findings.values()),
                    "activity": activity,
                    "research_task": outcome["research_task"],
                }

        if "blocks" in outcome:
            break

    return settle(state, transcript, outcome, activity, seen_findings)


def route_from_main(state):
    return "research" if state.get("research_task") else "done"
