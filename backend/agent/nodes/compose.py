from langchain_core.messages import AIMessage

from agent import llm
from agent.prompts import render_prompt
from agent.schemas import BLOCK_TYPES, AnswerComposition

PROSE_BLOCKS = ("summary", "gap")


def format_findings(findings):
    if not findings:
        return "(the dossier holds nothing relevant to this question)"

    entries = []
    for finding in findings:
        lines = [
            f"- id: {finding['id']}",
            f"  claim: {finding['claim']}",
            f"  source: {finding['source']}",
            f"  date: {finding.get('date')}",
            f"  status: {'active' if finding.get('active', True) else 'superseded'}",
        ]
        if finding.get("supersedes"):
            lines.append(f"  replaces: {finding['supersedes']}")
        if finding.get("superseded_by"):
            lines.append(f"  replaced by: {finding['superseded_by']}")
        entries.append("\n".join(lines))
    return "\n".join(entries)


def hydrate_blocks(specs, findings):
    by_id = {finding["id"]: finding for finding in findings}
    blocks = []
    dropped = []

    for spec in specs:
        if spec.type not in BLOCK_TYPES:
            continue

        resolved = []
        for finding_id in spec.finding_ids:
            finding = by_id.get(finding_id)
            if finding is None:
                dropped.append(finding_id)
            else:
                resolved.append(finding)

        text = (spec.text or "").strip()
        if not text and not resolved:
            continue

        blocks.append({"type": spec.type, "text": text or None, "findings": resolved})

    return blocks, dropped


def nothing_to_show(findings):
    if findings:
        return {"type": "findings", "text": None, "findings": findings}
    return {
        "type": "gap",
        "text": "The dossier does not hold any finding on this yet.",
        "findings": [],
    }


def refuse_unsupported_claim(asserted_claim):
    quoted = f' ("{asserted_claim}")' if asserted_claim else ""
    return {
        "type": "gap",
        "text": (
            f"The dossier holds no finding supporting that{quoted}. Nothing on record was ever "
            "researched or written down to that effect, so I cannot confirm it. I can research it "
            "now if you want it established."
        ),
        "findings": [],
    }


def compose_answer(state):
    findings = state.get("retrieved_findings", [])

    if state.get("intent") == "memory_probe" and not findings:
        block = refuse_unsupported_claim(state.get("asserted_claim"))
        return {
            "blocks": [block],
            "dropped_finding_ids": [],
            "final_answer": block["text"],
            "messages": [AIMessage(block["text"])],
        }

    prompt = render_prompt(
        "compose",
        query=state["user_query"],
        intent=state.get("intent", "research"),
        asserted_claim=state.get("asserted_claim") or "(none)",
        findings=format_findings(findings),
    )

    composition = llm.get_structured_llm(AnswerComposition).invoke(prompt)
    blocks, dropped = hydrate_blocks(composition.blocks, findings)

    if not blocks:
        blocks = [nothing_to_show(findings)]

    answer = " ".join(
        block["text"] for block in blocks if block["type"] in PROSE_BLOCKS and block["text"]
    )

    return {
        "blocks": blocks,
        "dropped_finding_ids": dropped,
        "final_answer": answer,
        "messages": [AIMessage(answer or "See the findings below.")],
    }
