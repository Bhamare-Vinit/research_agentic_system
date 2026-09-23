from agent import llm
from agent.prompts import render_prompt
from agent.schemas import QueryUnderstanding
from agent.tools import storage

HISTORY_TURNS = 8


def format_structure(structure):
    if not structure:
        return "(the dossier is empty, nothing has been researched yet)"
    lines = []
    for topic, categories in structure.items():
        summary = ", ".join(
            f"{information} ({count})" for information, count in categories.items()
        )
        lines.append(f"- {topic}: {summary}")
    return "\n".join(lines)


def format_history(messages):
    recent = messages[-HISTORY_TURNS:]
    if not recent:
        return "(this is the first message of the session)"
    lines = []
    for message in recent:
        speaker = "user" if getattr(message, "type", "") == "human" else "dossier"
        lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)


def normalise_dimensions(dimensions):
    seen = []
    for dimension in dimensions or []:
        key = storage.slugify(dimension)
        if key not in seen:
            seen.append(key)
    return seen[:4] or ["general"]


def understand_query(state):
    prompt = render_prompt(
        "understand",
        structure=format_structure(state.get("dossier_structure", {})),
        history=format_history(state.get("messages", [])[:-1]),
        query=state["user_query"],
    )

    understanding = llm.get_structured_llm(QueryUnderstanding).invoke(prompt)

    return {
        "topic": storage.slugify(understanding.topic),
        "information": normalise_dimensions(understanding.information),
        "intent": understanding.intent,
        "asserted_claim": understanding.asserted_claim,
    }
