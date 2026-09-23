from agent import llm
from agent.prompts import render_prompt
from agent.schemas import Decision
from agent.settings import MAX_RESEARCH_ITERATIONS
from agent.tools import storage


def format_findings(findings):
    if not findings:
        return "(nothing in the dossier matches this question yet)"
    lines = []
    for finding in findings:
        status = "active" if finding.get("active", True) else "superseded"
        lines.append(
            f"- [{finding.get('id')}] ({status}, found {finding.get('date')}) {finding.get('claim')}"
        )
    return "\n".join(lines)


def format_research_log(entries):
    if not entries:
        return "(no research has run yet this turn)"
    return "\n".join(f"- {entry.get('summary', entry)}" for entry in entries)


def settled(decision, reason):
    return {"decision": decision, "decision_reason": reason, "research_task": None}


def decide(state):
    iteration = state.get("iteration", 0)

    if state.get("intent") == "memory_probe":
        return settled(
            "answer",
            "the user attributed a claim to Dossier, which is checked against stored findings rather than researched",
        )

    if iteration >= MAX_RESEARCH_ITERATIONS:
        return settled(
            "answer",
            f"reached the safety maximum of {MAX_RESEARCH_ITERATIONS} research passes",
        )

    if iteration > 0 and not state.get("findings_added"):
        return settled(
            "answer",
            "the last research pass added no new findings, so answering from what the dossier already holds",
        )

    prompt = render_prompt(
        "decide",
        query=state["user_query"],
        intent=state.get("intent", "research"),
        iteration=iteration,
        max_iterations=MAX_RESEARCH_ITERATIONS,
        research_log=format_research_log(state.get("research_log", [])),
        findings=format_findings(state.get("retrieved_findings", [])),
    )

    verdict = llm.get_structured_llm(Decision).invoke(prompt)

    if verdict.decision != "research":
        return settled("answer", verdict.reason)

    task = verdict.research_task
    if task is None:
        return settled(
            "answer", "the planner asked to research but named nothing specific to look for"
        )

    return {
        "decision": "research",
        "decision_reason": verdict.reason,
        "research_task": {
            "topic": storage.slugify(task.topic or state.get("topic")),
            "information": storage.slugify(task.information),
            "research_question": task.research_question,
        },
    }


def route_from_decision(state):
    return "research" if state.get("decision") == "research" else "answer"
