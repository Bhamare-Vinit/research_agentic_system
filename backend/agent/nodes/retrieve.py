from agent import tokens
from agent.tools import dossier_tools, storage

FALLBACK_CATEGORY_LIMIT = 4

HISTORY_QUESTION_WORDS = (
    "change",
    "changed",
    "update",
    "updated",
    "revised",
    "contradict",
    "why",
    "instead",
    "previously",
    "earlier",
    "used to",
)


def load_structure(state):
    return {"dossier_structure": dossier_tools.get_dossier_structure()}


def asks_about_a_change(query):
    lowered = str(query or "").lower()
    return any(word in lowered for word in HISTORY_QUESTION_WORDS)


def retrieve_dossier(state):
    topic = state.get("topic")
    dimensions = state.get("information") or ["general"]
    include_inactive = asks_about_a_change(state.get("user_query"))

    findings = []
    per_dimension = {}

    for dimension in dimensions:
        retrieved = dossier_tools.get_dossier(
            topic, dimension, include_inactive=include_inactive
        )
        findings.extend(retrieved["findings"])
        per_dimension[dimension] = {
            "total_available": retrieved["total_available"],
            "returned": retrieved["returned"],
        }

    fell_back_to = []
    if not findings and state.get("intent") != "memory_probe":
        known = dossier_tools.get_dossier_structure().get(topic, {})
        ranked = sorted(known.items(), key=lambda entry: entry[1], reverse=True)
        for dimension, _ in ranked[:FALLBACK_CATEGORY_LIMIT]:
            if dimension in per_dimension:
                continue
            retrieved = dossier_tools.get_dossier(
                topic, dimension, include_inactive=include_inactive
            )
            if not retrieved["findings"]:
                continue
            findings.extend(retrieved["findings"])
            per_dimension[dimension] = {
                "total_available": retrieved["total_available"],
                "returned": retrieved["returned"],
            }
            fell_back_to.append(dimension)

    whole_dossier_tokens = tokens.count_tokens(storage.load_dossier())
    retrieved_tokens = tokens.count_tokens(findings)

    return {
        "retrieved_findings": findings,
        "retrieval_stats": {
            "topic": topic,
            "dimensions": per_dimension,
            "included_superseded": include_inactive,
            "fell_back_to": fell_back_to,
            "whole_dossier_tokens": whole_dossier_tokens,
            "retrieved_tokens": retrieved_tokens,
            "tokens_saved_pct": (
                round(100 * (1 - retrieved_tokens / whole_dossier_tokens), 1)
                if whole_dossier_tokens
                else 0.0
            ),
        },
    }
