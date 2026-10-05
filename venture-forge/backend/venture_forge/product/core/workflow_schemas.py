from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import Field, model_validator
from .schemas import Input


class Command(Input):
    expected_revision: int = Field(ge=1)


class ConceptUpdate(Command):
    name: str = Field(min_length=2, max_length=120)
    idea: str = Field(min_length=10, max_length=2000)
    customer_segment: str = Field(min_length=3, max_length=300)
    geography: str = Field(min_length=2, max_length=120)


class ReceiptCreate(Command):
    hypothesis_id: str
    title: str = Field(min_length=3, max_length=300)
    kind: Literal["source", "interview", "observation"] = "source"
    content: str = Field(min_length=10, max_length=20000)
    locator: str = Field(min_length=2, max_length=2000)
    relation: Literal["supports", "contradicts", "contextualizes"] = "contextualizes"
    limitations: str = Field(min_length=3, max_length=2000)
    consent: Literal["public_source", "notes_only", "quote_permitted", "private_observation"]
    participant_code: str | None = Field(default=None, min_length=2, max_length=60)
    collected_on: date

    @model_validator(mode="after")
    def consent_scope(self):
        if self.kind == "interview" and (not self.participant_code or self.consent not in {"notes_only", "quote_permitted"}):
            raise ValueError("Interviews require a participant code and explicit notes/quote consent.")
        if self.collected_on > date.today():
            raise ValueError("Evidence cannot be collected in the future.")
        return self


class FinanceInputs(Input):
    price: Decimal = Field(ge=0, le=10**12)
    volume: int = Field(ge=0, le=10**9)
    direct_cost: Decimal = Field(ge=0, le=10**12)
    fixed_cost: Decimal = Field(ge=0, le=10**12)
    collected_cash: Decimal = Field(ge=0, le=10**12)
    cash_balance: Decimal = Field(ge=0, le=10**12)
    period: Literal["month", "year", "cohort"] = "month"
    acquisition_spend: Decimal | None = Field(default=None, ge=0, le=10**12, description="Sales and marketing acquisition spend in INR for this period. Classify costs already included in the scenario; this field does not add another cash outflow.")
    new_customers: int | None = Field(default=None, ge=0, le=10**9, description="New paying customers acquired in the same period as acquisition spend. Zero leaves CAC undefined.")
    average_revenue_per_customer: Decimal | None = Field(default=None, ge=0, le=10**12, description="Average revenue per customer in INR per selected month or year; used only for the explicit lifetime-value estimate.")
    customer_lifetime_periods: Decimal | None = Field(default=None, gt=0, le=10**6, description="Assumed customer lifetime in the same month/year units as the selected period. Missing inputs leave LTV unknown.")

    @model_validator(mode="after")
    def unit_economics_scope(self):
        if self.acquisition_spend is not None and self.acquisition_spend > self.direct_cost + self.fixed_cost:
            raise ValueError("Acquisition spend must already be included in the scenario's direct and fixed costs.")
        if self.period == "cohort" and (self.average_revenue_per_customer is not None or self.customer_lifetime_periods is not None):
            raise ValueError("LTV requires a month or year period so revenue and customer lifetime use the same units.")
        return self


class MarketInputs(Input):
    total_accounts: int = Field(ge=0, le=10**9)
    serviceable_accounts: int = Field(ge=0, le=10**9)
    reachable_accounts: int = Field(ge=0, le=10**9)
    capacity: int = Field(ge=0, le=10**9)
    price: Decimal = Field(ge=0, le=10**12)
    unit: str = Field(min_length=2, max_length=100)
    period: Literal["month", "year", "cohort"] = "year"

    @model_validator(mode="after")
    def cascade(self):
        if self.serviceable_accounts > self.total_accounts:
            raise ValueError("Serviceable accounts cannot exceed the total account universe.")
        return self


class ArtifactCreate(Command):
    capability: Literal["market", "finance", "simulation", "model", "competitor", "academy", "ecosystem", "investor"]
    title: str = Field(min_length=3, max_length=300)
    inputs: dict
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


class WorksheetInputs(Input):
    fields: dict[str, str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def bounded(self):
        if any(len(k) > 100 or len(v) > 4000 for k, v in self.fields.items()):
            raise ValueError("Worksheet values exceed the limit.")
        return self


class Protocol(Input):
    intervention: str = Field(min_length=10, max_length=2000)
    metric: str = Field(min_length=3, max_length=300)
    threshold_percent: Decimal = Field(ge=0, le=100)
    minimum_n: int = Field(ge=1, le=100000)
    end_date: date
    stop_rule: str = Field(min_length=3, max_length=1000)


class ExperimentCreate(Command):
    hypothesis_id: str
    title: str = Field(min_length=3, max_length=300)
    protocol: Protocol


class ObservationCreate(Command):
    participant_code: str = Field(min_length=2, max_length=60)
    receipt_id: str
    success: bool
    instrument_valid: bool = True
    deviation: str = Field(default="", max_length=2000)


class DecisionCreate(Command):
    target_type: Literal["experiment", "artifact", "run"]
    target_id: str
    choice: Literal["continue", "revise", "stop", "accept", "reject"]
    rationale: str = Field(min_length=10, max_length=4000)


class RunCreate(Command):
    hypothesis_id: str
    capability: Literal["research", "customer", "model"] = "research"
    objective: str = Field(min_length=10, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    external_actions: Literal[False] = False
    max_cost_inr: Literal[0] = 0
