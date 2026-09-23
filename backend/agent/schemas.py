from typing import Literal, Optional

from pydantic import BaseModel, Field

INTENTS = ("research", "recall", "memory_probe", "followup")
BLOCK_TYPES = ("summary", "findings", "sources", "gap", "update")


class QueryUnderstanding(BaseModel):
    topic: str = Field(
        description="snake_case topic key. Reuse an existing key from the dossier structure whenever the question is about that same subject."
    )
    information: list[str] = Field(
        description="one to four snake_case information dimensions such as cost, commercial_readiness, manufacturers"
    )
    intent: Literal["research", "recall", "memory_probe", "followup"] = Field(
        description="research for new information, recall for what we already found, memory_probe when the user attributes a past statement to you, followup when narrowing the current topic"
    )
    asserted_claim: Optional[str] = Field(
        default=None,
        description="the exact claim the user is attributing to you, set only when intent is memory_probe",
    )
    reasoning: str = Field(description="one sentence explaining the classification")


class ResearchTask(BaseModel):
    topic: str
    information: str
    research_question: str = Field(
        description="a specific question the research agent should answer from live sources"
    )


class Decision(BaseModel):
    decision: Literal["answer", "research"]
    reason: str = Field(description="one sentence justifying the decision")
    research_task: Optional[ResearchTask] = Field(
        default=None, description="required when decision is research"
    )


class BlockSpec(BaseModel):
    type: Literal["summary", "findings", "sources", "gap", "update"]
    text: Optional[str] = Field(
        default=None, description="prose for summary and gap blocks"
    )
    finding_ids: list[str] = Field(
        default_factory=list,
        description="ids copied verbatim from the findings you were given. Never invent an id.",
    )


class AnswerComposition(BaseModel):
    blocks: list[BlockSpec] = Field(
        description="the blocks that best present this particular answer"
    )
