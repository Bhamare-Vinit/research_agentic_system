import json

from langchain_core.messages import HumanMessage

from agent import settings
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
            }

    if turns and turns[-1]["answer"] and values.get("blocks"):
        turns[-1]["answer"]["blocks"] = values["blocks"]
        turns[-1]["answer"]["retrieval_stats"] = values.get("retrieval_stats", {})
        turns[-1]["answer"]["iterations"] = values.get("iteration", 0)

    return {"thread_id": thread_id, "turns": turns}


def sse(payload):
    return f"data: {json.dumps(payload, default=str)}\n\n"


def describe_research_entry(entry):
    event = {"type": "step", "tool": entry.get("tool"), "message": entry.get("summary")}
    if entry.get("finding_id"):
        event["finding_id"] = entry["finding_id"]
        event["source"] = entry.get("source")
    return event


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
    }

    yield sse({"type": "status", "node": "start", "message": "Opening the dossier"})

    try:
        for update in get_graph().stream(state, config=config, stream_mode="updates"):
            for node, payload in update.items():
                yield sse(
                    {"type": "status", "node": node, "message": NODE_LABELS.get(node, node)}
                )
                if not isinstance(payload, dict):
                    continue

                if node == "understand_query":
                    yield sse(
                        {
                            "type": "understanding",
                            "topic": payload.get("topic"),
                            "information": payload.get("information"),
                            "intent": payload.get("intent"),
                        }
                    )

                if node == "retrieve_dossier":
                    answer["retrieval_stats"] = payload.get("retrieval_stats", {})
                    yield sse(
                        {"type": "retrieval", "stats": answer["retrieval_stats"]}
                    )

                if node == "decide":
                    yield sse(
                        {
                            "type": "decision",
                            "decision": payload.get("decision"),
                            "reason": payload.get("decision_reason"),
                        }
                    )

                if node == "research":
                    answer["iterations"] = payload.get("iteration", answer["iterations"])
                    for entry in payload.get("research_log", []):
                        yield sse(describe_research_entry(entry))

                if node == "compose_answer":
                    answer["blocks"] = payload.get("blocks", [])
                    answer["final_answer"] = payload.get("final_answer", "")
                    answer["dropped_finding_ids"] = payload.get("dropped_finding_ids", [])
    except Exception as failure:
        yield sse({"type": "error", "message": str(failure)})
        return

    yield sse({"type": "done", "thread_id": thread_id, **answer})
