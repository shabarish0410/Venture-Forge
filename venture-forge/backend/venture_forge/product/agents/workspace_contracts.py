"""Versioned founder MVP inputs. Persisted inside reviewed specialist artifacts."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import Field, model_validator
from venture_forge.product.core.schemas import Input

Text = Annotated[str, Field(max_length=2000)]
Short = Annotated[str, Field(max_length=300)]
Money = Annotated[Decimal, Field(ge=0, le=10**12, allow_inf_nan=False)]


class EvidenceLink(Input):
    source_id: str | None = Field(default=None, max_length=80)
    quote: Text = ""


class Unknown(Input):
    question: Short
    impact: int = Field(default=3, ge=1, le=5)
    uncertainty: int = Field(default=3, ge=1, le=5)
    owner: Short = "Founder"
    due_on: date | None = None
    deferred_reason: Short = ""


class Task(Input):
    action: Short
    completion_evidence: Short
    status: Literal["planned", "completed", "abandoned"] = "planned"
    source_id: str | None = None
    resolution: Text = ""


class HomeWorkspace(Input):
    entry_path: Literal["idea", "problem", "technology", "research", "entrepreneur"] = "idea"
    founder_goal: Text = ""
    available_hours: int | None = Field(default=None, ge=0, le=168)
    budget_inr: Money | None = None
    payer: Short = "unknown"
    approver: Short = "unknown"
    unknowns: list[Unknown] = Field(default_factory=list, max_length=30)
    mission_reason: Text = ""
    mission_completion: Text = ""
    tasks: list[Task] = Field(default_factory=list, max_length=20)


class SourceReview(Input):
    source_id: str
    source_type: Literal["primary", "official", "secondary", "unknown"] = "unknown"
    publisher: Short = "unknown"
    geography: Short = "unknown"
    method: Text = "unknown"
    volatility: Literal["stable", "price", "deadline", "policy"] = "stable"
    published_on: date | None = None
    review_note: Text = ""


class Claim(EvidenceLink):
    statement: Text
    claim_type: Literal["source_reported", "founder_assumption", "inference"] = "source_reported"
    relation: Literal["supports", "contradicts", "contextualizes"] = "contextualizes"
    limitation: Text = ""


class ResearchWorkspace(Input):
    decision: Text = ""
    scope: Text = ""
    exclusions: Text = ""
    geography: Short = ""
    period: Short = ""
    subquestions: list[Short] = Field(default_factory=list, max_length=10)
    source_reviews: list[SourceReview] = Field(default_factory=list, max_length=30)
    claims: list[Claim] = Field(default_factory=list, max_length=30)


class ValueChainActor(Input):
    actor: Short
    role: Literal["supplier", "user", "buyer", "payer", "approver", "beneficiary", "partner", "gatekeeper"]
    gives: Short = "unknown"
    receives: Short = "unknown"
    depends_on: Short = "unknown"


class Segment(EvidenceLink):
    name: Short
    criteria: Text
    need: Text = "unknown"
    access: Text = "unknown"
    exclusion: Text = ""


class DriverSource(EvidenceLink):
    driver: Short
    definition: Text = ""
    unit: Short = ""
    owner: Short = "Founder"


class MarketWorkspace(Input):
    category: Short = ""
    buyer: Short = "unknown"
    inclusions: Text = ""
    exclusions: Text = ""
    value_chain: list[ValueChainActor] = Field(default_factory=list, max_length=20)
    segments: list[Segment] = Field(default_factory=list, max_length=20)
    selected_segment: Short = ""
    selection_reason: Text = ""
    driver_sources: list[DriverSource] = Field(default_factory=list, max_length=15)


class InterviewQuestion(Input):
    question: Short
    purpose: Short


class CodedObservation(EvidenceLink):
    theme: Short
    role: Literal["user", "buyer", "payer", "approver", "blocker", "beneficiary", "unknown"] = "unknown"
    kind: Literal["past_behavior", "workaround", "cost", "objection", "opinion", "hypothetical_intent"] = "past_behavior"


class CustomerWorkspace(Input):
    mode: Literal["synthesis", "plan"] = "synthesis"
    decision: Text = ""
    target_segment: Short = ""
    recruitment_criteria: Text = ""
    recruitment_bias: Text = "unknown"
    guide: list[InterviewQuestion] = Field(default_factory=list, max_length=20)
    observations: list[CodedObservation] = Field(default_factory=list, max_length=50)
    decision_choice: Literal["pending", "continue", "revise", "pivot", "stop", "another_round"] = "pending"
    decision_reason: Text = ""
    next_test: Text = ""


class CompetitorProfile(EvidenceLink):
    alternative: Short
    workflow: Text = "unknown"
    capabilities: Text = "unknown"
    customer_tier: Short = "unknown"
    price_period: Literal["month", "year", "one_time", "unknown"] = "unknown"
    price_unit: Short = "unknown"
    included_services: Text = "unknown"
    setup_fee_inr: Money | None = None


class Differentiation(EvidenceLink):
    benefit: Text
    segment: Short
    proof_needed: Text
    disconfirming_test: Text


class CompetitorWorkspace(Input):
    customer_job: Text = ""
    profiles: list[CompetitorProfile] = Field(default_factory=list, max_length=20)
    status_quo: Text = "unknown"
    non_consumption: Text = "unknown"
    differentiation: list[Differentiation] = Field(default_factory=list, max_length=10)


Relationship = Literal["unknown", "b2b", "b2c", "c2c", "b2b2c", "d2c"]
Operating = Literal["unknown", "marketplace", "api_platform", "franchise", "wholesale", "retail", "manufacturing", "direct_service"]
Delivery = Literal["unknown", "saas", "licensing", "data_insights", "ai_service", "physical_product", "managed_service"]
Pricing = Literal["unknown", "subscription", "freemium", "usage_based", "per_user", "commission", "transaction_fee", "lead_generation", "advertising", "outcome_based", "one_time"]


class ModelOption(Input):
    name: Short
    relationship: Relationship = "unknown"
    operating: Operating = "unknown"
    delivery: Delivery = "unknown"
    pricing: Pricing = "unknown"
    payer: Short = "unknown"
    revenue_unit: Short = "unknown"
    price_inr: Money | None = None
    units_per_period: int | None = Field(default=None, ge=0, le=10**9)
    period: Literal["month", "year", "cohort"] = "month"
    payment_delay_days: int | None = Field(default=None, ge=0, le=365)
    channel: Short = "unknown"
    benefit: Text = "unknown"
    risk: Text = "unknown"
    first_test: Text = ""


class CanvasEntry(EvidenceLink):
    block: Literal["customer_segments", "value_propositions", "channels", "customer_relationships", "revenue_streams", "key_resources", "key_activities", "key_partners", "cost_structure"]
    value: Text
    owner: Short = "Founder"
    test: Text = ""


class ModelWorkspace(Input):
    stakeholders: list[ValueChainActor] = Field(default_factory=list, max_length=20)
    options: list[ModelOption] = Field(default_factory=list, max_length=3)
    canvas: list[CanvasEntry] = Field(default_factory=list, max_length=9)
    selected_option: Short = ""
    decision_reason: Text = ""
    pricing_behavior: Text = ""
    pricing_threshold: Text = ""

    @model_validator(mode="after")
    def unambiguous_options(self):
        names = [item.name for item in self.options]
        if len(names) != len(set(names)):
            raise ValueError("Model option names must be unique")
        if self.selected_option and self.selected_option not in names:
            raise ValueError("Select a named model option")
        if len({item.block for item in self.canvas}) != len(self.canvas):
            raise ValueError("Each canvas block can be entered once")
        return self


class FinanceWorkspace(Input):
    months: int = Field(default=12, ge=1, le=36)
    monthly_volume_growth_percent: Decimal = Field(default=Decimal(0), ge=-100, le=100, allow_inf_nan=False)
    collection_delay_months: int = Field(default=0, ge=0, le=12)
    collection_percent: Decimal | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    low_volume_factor: Decimal = Field(default=Decimal("0.8"), ge=0, le=1, allow_inf_nan=False)
    high_volume_factor: Decimal = Field(default=Decimal("1.2"), ge=1, le=10, allow_inf_nan=False)
    assumption_sources: list[DriverSource] = Field(default_factory=list, max_length=20)


class Risk(Input):
    assumption: Text
    category: Literal["desirability", "viability", "feasibility", "channel", "ethical"]
    impact: int = Field(default=3, ge=1, le=5)
    uncertainty: int = Field(default=3, ge=1, le=5)
    test: Text = ""


class ExperimentWorkspace(Input):
    risks: list[Risk] = Field(default_factory=list, max_length=20)
    pattern: Literal["concierge", "wizard_of_oz", "landing_page", "prototype", "smoke_test", "pre_order", "pilot", "no_code", "manual_service", "single_feature"] = "concierge"
    target_customer: Short = ""
    core_promise: Text = ""
    included_scope: Text = ""
    non_goals: Text = ""
    tasks: list[Task] = Field(default_factory=list, max_length=20)


class SimulationRound(Input):
    price_factor: Decimal = Field(default=Decimal(1), ge=0, le=10, allow_inf_nan=False)
    demand_factor: Decimal = Field(default=Decimal(1), ge=0, le=10, allow_inf_nan=False)
    channel_spend_inr: Money = Decimal(0)
    channel_customers: int = Field(default=0, ge=0, le=10**6)
    event: Literal["none", "demand_down_20", "direct_cost_up_20"] = "none"
    rationale: Text
    debrief: Text = ""


class SimulationWorkspace(Input):
    learning_objective: Text = ""
    capacity: int | None = Field(default=None, ge=0, le=10**9)
    rounds: list[SimulationRound] = Field(default_factory=list, max_length=12)
    replay_label: Short = "Original"


class AcademyWorkspace(Input):
    current_task: Text = ""
    diagnostic: Text = ""
    rationale: Text = ""
    self_review: Text = ""
    next_application: Text = ""


class EligibilityRule(EvidenceLink):
    opportunity: Short
    requirement: Text
    result: Literal["pass", "fail", "unknown"] = "unknown"
    evidence: Text = ""


class EcosystemWorkspace(Input):
    need: Short = ""
    state_or_ut: Short = ""
    national_only: bool = False
    eligibility_rules: list[EligibilityRule] = Field(default_factory=list, max_length=40)
    saved_opportunities: list[Short] = Field(default_factory=list, max_length=10)


class PitchClaim(EvidenceLink):
    section: Literal["problem", "customer", "solution", "market", "model", "traction", "finance", "team", "ask", "risks"]
    statement: Text
    classification: Literal["source_reported", "assumption", "projection"] = "assumption"
    artifact_id: str | None = None


class Rehearsal(Input):
    question: Short
    answer: Text
    rationale: Text = ""


class InvestorWorkspace(Input):
    why_now: Text = ""
    alternative_plan: Text = ""
    use_of_funds: Text = ""
    pitch_claims: list[PitchClaim] = Field(default_factory=list, max_length=20)
    rehearsal: list[Rehearsal] = Field(default_factory=list, max_length=10)


class PassportWorkspace(Input):
    next_action: Literal["customer_discovery", "mvp_test", "financial_planning", "funding_preparation"] = "mvp_test"


WORKSPACES = dict(zip(
    ["home", "research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "academy", "ecosystem", "investor", "passport"],
    [HomeWorkspace, ResearchWorkspace, MarketWorkspace, CustomerWorkspace, CompetitorWorkspace, ModelWorkspace, FinanceWorkspace, ExperimentWorkspace, SimulationWorkspace, AcademyWorkspace, EcosystemWorkspace, InvestorWorkspace, PassportWorkspace],
))


class ReportSection(Input):
    key: str
    title: str
    description: str = ""
    rows: list[dict[str, str | int | bool | None]] = Field(default_factory=list)


class WorkspaceReport(Input):
    version: Literal["founder-mvp-v1"] = "founder-mvp-v1"
    sections: list[ReportSection]
    gaps: list[str] = Field(default_factory=list)
    next_action: str
