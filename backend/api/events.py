import json

from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.messages import HumanMessage

from agent import settings, tokens
from agent.checkpoint import get_checkpointer
from agent.graph import NODE_LABELS, build_graph, initial_state

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(get_checkpointer())
    return _graph


def replay_thread(thread_id):
    snapshot = get_graph().get_state({"configurable": {"thread_id": thread_id}})
    values = getattr(snapshot, "values", None) or {}

    turns = []
    for message in values.get("messages", []):
        speaker = getattr(message, "type", "")
        if speaker == "human":
            turns.append({"query": message.content, "answer": None})
        elif speaker == "ai" and turns:
            turns[-1]["answer"] = {
                "final_answer": message.content,
                "blocks": [],
                "dropped_finding_ids": [],
                "retrieval_stats": {},
                "iterations": 0,
                "llm": {},
            }

    if turns and turns[-1]["answer"] and values.get("blocks"):
        turns[-1]["answer"]["blocks"] = values["blocks"]
        turns[-1]["answer"]["retrieval_stats"] = values.get("retrieval_stats", {})
        turns[-1]["answer"]["iterations"] = values.get("iteration", 0)

    return {"thread_id": thread_id, "turns": turns}


def sse(payload):
    return f"data: {json.dumps(payload, default=str)}\n\n"


def describe_activity(entry):
    event = {
        "type": "step",
        "agent": entry.get("agent"),
        "tool": entry.get("tool"),
        "message": entry.get("summary"),
    }
    if entry.get("finding_id"):
        event["finding_id"] = entry["finding_id"]
        event["source"] = entry.get("source")
    return event


def node_events(node, payload, answer):
    events = [{"type": "status", "node": node, "message": NODE_LABELS.get(node, node)}]
    if not isinstance(payload, dict):
        return events

    events.extend(describe_activity(entry) for entry in payload.get("activity", []))

    task = payload.get("research_task")
    if task:
        events.append(
            {
                "type": "decision",
                "decision": "research",
                "reason": task.get("research_question", ""),
            }
        )

    if node == "research_agent":
        answer["iterations"] = payload.get("iteration", answer["iterations"])

    if payload.get("blocks"):
        answer["blocks"] = payload["blocks"]
        answer["final_answer"] = payload.get("final_answer", "")
        answer["dropped_finding_ids"] = payload.get("dropped_finding_ids", [])
        answer["retrieval_stats"] = payload.get("retrieval_stats", {})
        events.append(
            {
                "type": "decision",
                "decision": "answer",
                "reason": "the case file holds enough to answer",
            }
        )
        events.append({"type": "retrieval", "stats": answer["retrieval_stats"]})

    return events


def run_stream(query, thread_id):
    state = initial_state(query)
    state["messages"] = [HumanMessage(query)]
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "dossier_turn",
        "tags": ["dossier", f"thread:{thread_id}"],
        "metadata": {
            "thread_id": thread_id,
            "user_query": query,
            "provider": settings.active_provider(),
            "model": settings.active_model(),
        },
    }

    answer = {
        "blocks": [],
        "final_answer": "",
        "dropped_finding_ids": [],
        "retrieval_stats": {},
        "iterations": 0,
        "llm": {},
    }

    yield sse({"type": "status", "node": "start", "message": "Opening the case file"})

    try:
        with get_usage_metadata_callback() as usage:
            for update in get_graph().stream(state, config=config, stream_mode="updates"):
                for node, payload in update.items():
                    for event in node_events(node, payload, answer):
                        yield sse(event)
    except Exception as failure:
        yield sse({"type": "error", "message": str(failure)})
        return

    answer["llm"] = tokens.summarise_usage(usage.usage_metadata)

    tokens.record_turn(
        {
            "thread_id": thread_id,
            "query": query,
            "iterations": answer["iterations"],
            "retrieval": answer["retrieval_stats"],
            "llm": answer["llm"],
        }
    )

    yield sse({"type": "done", "thread_id": thread_id, **answer})
