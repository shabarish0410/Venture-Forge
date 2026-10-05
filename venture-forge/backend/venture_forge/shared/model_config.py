"""Operator-declared capabilities; no specialist names or vendor-specific model IDs."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["openai", "anthropic", "gemini", "ollama"]
Reasoning = Literal["basic", "standard", "high"]


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    provider: Provider
    model_id: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_.:/-]+$")
    reasoning: Reasoning = "standard"
    context_tokens: int = Field(default=32768, ge=1024, le=2000000)
    max_output_tokens: int = Field(default=2048, ge=256, le=32768)
    structured_outputs: bool = True
    tool_calling: bool = False
    input_inr_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    output_inr_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    priority: int = Field(default=100, ge=0, le=1000)
    enabled: bool = True


class ModelRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task: Literal["guidance", "synthesis", "reasoning", "explanation", "diligence"]
    reasoning: Reasoning
    min_context_tokens: int = Field(ge=1024)
    max_output_tokens: int = Field(default=2048, ge=256, le=4096)
    structured_outputs: bool = True
    tool_calling: bool = False
    deterministic_operations: tuple[str, ...]
