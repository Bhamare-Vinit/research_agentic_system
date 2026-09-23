import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class DossierState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_query: str
    intent: str
    topic: Optional[str]
    information: list[str]
    asserted_claim: Optional[str]
    dossier_structure: dict
    retrieved_findings: list[dict]
    retrieval_stats: dict
    research_task: Optional[dict]
    research_log: Annotated[list[dict], operator.add]
    findings_added: int
    decision: Optional[str]
    decision_reason: Optional[str]
    iteration: int
    blocks: list[dict]
    final_answer: Optional[str]
    token_usage: dict
