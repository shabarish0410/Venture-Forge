from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().lower()


class Register(Login):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=15, max_length=128)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter your name")
        return value.strip()


class PasswordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    password: str = Field(min_length=15, max_length=128)
    current_password: str | None = Field(default=None, min_length=1, max_length=256)


class FounderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    avatar_url: str | None = None
    onboarding_completed: bool
    has_password: bool
    created_at: datetime
    last_login_at: datetime | None = None
    realm: Literal["product"] = "product"


class VentureCreate(Input):
    name: str = Field(min_length=2, max_length=120)
    idea: str = Field(min_length=10, max_length=2000)
    customer_segment: str = Field(min_length=3, max_length=300)
    geography: str = Field(min_length=2, max_length=120)
    first_hypothesis: str = Field(min_length=10, max_length=1500)


class HypothesisCreate(Input):
    statement: str = Field(min_length=10, max_length=1500)
    category: Literal["problem", "customer", "pricing", "solution"] = "problem"
    expected_revision: int = Field(ge=1)


class VentureView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    idea: str
    customer_segment: str
    geography: str
    stage: str
    revision: int
    created_at: datetime
    updated_at: datetime


class HypothesisView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    statement: str
    category: str
    status: Literal["unvalidated"]
    origin: Literal["founder_asserted"]
    revision: int
    created_at: datetime


class ActivityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_type: str
    description: str
    created_at: datetime


class Passport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    realm: Literal["product"] = "product"
    venture: VentureView
    hypotheses: list[HypothesisView]
    activity: list[ActivityView]
    evidence_count: int = 0
    decision_count: int = 0
    evidence: list[dict] = Field(default_factory=list)
    artifacts: list[dict] = Field(default_factory=list)
    experiments: list[dict] = Field(default_factory=list)
    decisions: list[dict] = Field(default_factory=list)
    runs: list[dict] = Field(default_factory=list)
    completed_cycles: int = 0
    agent_runs: list[dict] = Field(default_factory=list)
    pipelines: list[dict] = Field(default_factory=list)
    handoffs: list[dict] = Field(default_factory=list)


class VentureList(BaseModel):
    ventures: list[VentureView]
