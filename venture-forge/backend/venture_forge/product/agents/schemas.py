from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from venture_forge.product.core.workflow_schemas import Command
from .registry import AgentId


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_steps: int = Field(default=12, ge=1, le=30)
    max_seconds: int = Field(default=60, ge=1, le=120)
    max_cost_inr: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)


class AgentRequest(Command):
    agent_id: AgentId
    objective: str = Field(min_length=10, max_length=2000)
    hypothesis_id: str
    parameters: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    artifact_ids: list[str] = Field(default_factory=list, max_length=40)
    experiment_ids: list[str] = Field(default_factory=list, max_length=20)
    stage_id: str | None = None
    supersedes_artifact_id: str | None = Field(default=None, max_length=36)
    mode: Literal["AUTO", "RULE", "MODEL"] = "AUTO"
    allow_model_processing: bool = False
    data_policy: Literal["cloud_allowed", "local_only"] = "cloud_allowed"
    preferred_profile: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    budget: Budget = Field(default_factory=Budget)
    external_actions: Literal[False] = False


class PipelineCreate(Command):
    template: Literal["first_evidence", "pivot", "learning", "funding", "complete"]
    objective: str = Field(min_length=10, max_length=2000)
    hypothesis_id: str


class AgentReview(Command):
    choice: Literal["accept", "reject"]
    rationale: str = Field(min_length=10, max_length=4000)
    expected_result_hash: str = Field(min_length=64, max_length=64)


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["specialist-v1"] = "specialist-v1"
    agent_id: AgentId
    specialist: str
    output_type: str
    status: Literal["PROPOSED", "NEEDS_INPUT"]
    summary: str
    data: dict
    evidence_ids: list[str]
    artifact_ids: list[str]
    unknowns: list[str]
    limitations: list[str]
    next_action: str
    handoffs: list[AgentId]
    evidence_class: Literal["FOUNDER_ASSUMPTION", "SOURCE_REPORTED", "CUSTOMER_REPORTED", "CALCULATED", "EXPERIMENT_RESULT", "SIMULATED", "PRACTICE", "DERIVED_VIEW"]
    mode: Literal["RULE", "MODEL"] = "RULE"

    @model_validator(mode="after")
    def specialist_contract(self):
        from .registry import REGISTRY
        from .outputs import validate_data
        spec = REGISTRY[self.agent_id]
        if self.specialist != spec.name or self.output_type != spec.output or self.handoffs != list(spec.sends):
            raise ValueError("Specialist identity, output or handoffs do not match its contract")
        validate_data(self.agent_id, self.data)
        return self


class SourceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=5, max_length=1500)
    source_id: str = Field(min_length=1, max_length=80)
    locator: str = Field(min_length=2, max_length=2000)
    quote: str = Field(min_length=5, max_length=600)


class ModelDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str = Field(min_length=10, max_length=4000)
    questions: list[str] = Field(max_length=5)
    evidence_ids: list[str] = Field(max_length=30)
    synthesis: str = Field(default="", max_length=6000)
    hypothesis_assessment: str = Field(default="", max_length=3000)
    claims: list[SourceClaim] = Field(default_factory=list, max_length=12)
    query_suggestions: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def bounded_questions(self):
        if any(len(q) > 500 for q in self.questions): raise ValueError("Question too long")
        if any(len(q) > 500 for q in self.query_suggestions): raise ValueError("Query too long")
        return self
