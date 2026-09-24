import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class DossierState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_query: str
    agent_messages: list
    retrieved_findings_cache: list[dict]
    activity: Annotated[list[dict], operator.add]
    research_task: Optional[dict]
    research_result: Optional[dict]
    findings_added: int
    iteration: int
    retrieval_stats: dict
    blocks: list[dict]
    dropped_finding_ids: list[str]
    final_answer: Optional[str]
