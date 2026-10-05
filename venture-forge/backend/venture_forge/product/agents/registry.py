from dataclasses import dataclass, replace
from typing import Literal
from decimal import Decimal
from datetime import date
from pydantic import Field
from venture_forge.product.core.schemas import Input
from venture_forge.product.core.workflow_schemas import FinanceInputs, MarketInputs
from venture_forge.shared.model_config import ModelRequirements

AgentId = Literal["home", "research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "academy", "ecosystem", "investor", "passport"]


class EmptyInputs(Input):
    pass


class ConceptInputs(Input):
    problem: str = Field(default="unknown", max_length=2000)
    solution: str = Field(default="unknown", max_length=2000)
    buyer: str = Field(default="unknown", max_length=300)
    beneficiary: str = Field(default="unknown", max_length=300)


class ResearchInputs(Input):
    freshness_days: int = Field(default=365, ge=1, le=3650)


class CustomerInputs(Input):
    invited: int = Field(default=0, ge=0, le=1000000)


class Rival(Input):
    name: str = Field(min_length=2, max_length=200)
    kind: Literal["direct", "indirect", "substitute", "status_quo", "non_consumption"]
    source_id: str | None = None
    price_inr: Decimal | None = Field(default=None, ge=0, le=10**12)
    switching_barrier: str = Field(default="unknown", max_length=1000)


class CompetitorInputs(Input):
    alternatives: list[Rival] = Field(default_factory=list, max_length=20)


class ModelInputs(Input):
    buyer: str = Field(default="unknown", max_length=300)
    value_proposition: str = Field(default="unknown", max_length=2000)
    relationship: Literal["direct", "subscription", "marketplace", "b2b2c", "unknown"] = "unknown"
    channel: str = Field(default="unknown", max_length=500)
    price_inr: Decimal | None = Field(default=None, ge=0, le=10**12)


class ExperimentInputs(Input):
    intervention: str = Field(default="unknown", max_length=2000)
    metric: str = Field(default="unknown", max_length=300)
    threshold_percent: Decimal | None = Field(default=None, ge=0, le=100)
    minimum_n: int | None = Field(default=None, ge=1, le=100000)
    end_date: date | None = None
    stop_rule: str = Field(default="unknown", max_length=1000)


class SimulationInputs(Input):
    price_factor: Decimal = Field(default=Decimal("1"), ge=0, le=10)
    volume_factor: Decimal = Field(default=Decimal("1"), ge=0, le=10)


class AcademyInputs(Input):
    topic: Literal["purpose", "problem", "customer", "research", "market", "competition", "model", "pricing", "finance", "experiments", "ecosystem", "funding"] = "experiments"
    independent_answer: str = Field(default="", max_length=4000)
    hints_used: int = Field(default=0, ge=0, le=100)
    return_to: AgentId = "home"


class Opportunity(Input):
    name: str = Field(min_length=2, max_length=200)
    official_url: str = Field(max_length=2000)
    source_id: str
    last_checked: date
    closes_on: date
    geography: str = Field(max_length=200)
    eligibility: Literal["confirmed", "unknown", "mismatch"] = "unknown"


class EcosystemInputs(Input):
    opportunities: list[Opportunity] = Field(default_factory=list, max_length=30)


class InvestorInputs(Input):
    milestone: str = Field(default="unknown", max_length=1000)
    amount_inr: Decimal | None = Field(default=None, ge=0, le=10**12)
    ownership_reviewed: bool = False
    ip_reviewed: bool = False


@dataclass(frozen=True)
class Specialist:
    id: str
    name: str
    workspace: str
    output: str
    tools: tuple[str, ...]
    receives: tuple[str, ...]
    sends: tuple[str, ...]
    schema: type[Input]
    description: str
    model_requirements: ModelRequirements | None = None


REGISTRY = {s.id: s for s in [
    Specialist("home", "ForgeGuide", "Mentor Home", "concept_map", ("concept.read", "mission.plan"), ("passport",), ("research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "academy", "ecosystem", "investor", "passport"), ConceptInputs, "Frame the founder's purpose, stakeholders and next evidence mission."),
    Specialist("research", "EvidenceScout", "Research Desk", "research_memo", ("evidence.read", "source.freshness", "contradiction.check"), ("home", "passport"), ("market", "competitor", "model", "finance", "ecosystem", "investor", "passport"), ResearchInputs, "Build a source-linked memo with explicit gaps and contradictions."),
    Specialist("market", "MarketMapper", "Market Lab", "market_definition", ("evidence.read", "market.calculate"), ("home", "research", "customer", "passport"), ("customer", "competitor", "model", "finance", "investor", "passport"), MarketInputs, "Calculate buying-unit TAM, SAM and capacity-capped SOM."),
    Specialist("customer", "CustomerLens", "Customer Lab", "customer_synthesis", ("interview.read", "consent.check", "interview.guide"), ("home", "market", "research", "passport"), ("model", "experiment", "academy", "passport"), CustomerInputs, "Summarize consented real observations and draft non-leading questions."),
    Specialist("competitor", "RivalRadar", "Competitor Room", "alternative_map", ("evidence.read", "alternative.compare"), ("home", "research", "market", "customer", "passport"), ("model", "experiment", "simulation", "investor", "passport"), CompetitorInputs, "Compare source-linked alternatives and switching barriers."),
    Specialist("model", "ModelArchitect", "Model Studio", "business_model", ("artifact.read", "canvas.build", "pricing.test"), ("home", "research", "market", "customer", "competitor", "finance", "passport"), ("finance", "experiment", "simulation", "academy", "passport"), ModelInputs, "Compare business models and build an evidence-linked canvas."),
    Specialist("finance", "FinancePilot", "Finance Lab", "financial_model", ("artifact.read", "finance.calculate"), ("home", "research", "market", "model", "experiment", "passport"), ("experiment", "simulation", "investor", "passport"), FinanceInputs, "Calculate revenue, margin, cash, runway, CAC and lifetime-value estimates from explicit drivers."),
    Specialist("experiment", "MVPForge", "MVP and Experiment Lab", "experiment_plan", ("artifact.read", "protocol.read", "result.compare"), ("home", "research", "market", "customer", "competitor", "model", "finance", "simulation", "passport"), ("home", "model", "finance", "academy", "passport"), ExperimentInputs, "Propose the smallest test or review a locked protocol and observations."),
    Specialist("simulation", "VentureSim", "Simulation Arena", "simulation_result", ("artifact.read", "scenario.calculate"), ("home", "model", "finance", "competitor", "passport"), ("academy", "experiment", "passport"), SimulationInputs, "Replay explicit price and volume changes using reviewed finance."),
    Specialist("academy", "SkillCoach", "Founder Academy", "learning_mission", ("lesson.lookup", "exercise.assess"), ("home", "customer", "model", "experiment", "simulation", "ecosystem", "investor", "passport"), ("home", "research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "ecosystem", "investor", "passport"), AcademyInputs, "Teach the concept needed for the next task and record assistance."),
    Specialist("ecosystem", "EcosystemNavigator", "Ecosystem Hub", "opportunity_shortlist", ("evidence.read", "opportunity.match", "freshness.check"), ("home", "research", "passport"), ("home", "academy", "investor", "passport"), EcosystemInputs, "Rank current supplied opportunities with eligibility and verification gaps."),
    Specialist("investor", "InvestorRoom", "Investor Room", "funding_readiness", ("artifact.read", "claim.reconcile", "diligence.check"), ("home", "research", "market", "competitor", "finance", "ecosystem", "passport"), ("home", "research", "academy", "passport"), InvestorInputs, "Prepare funding gaps and reconcile reviewed figures without promising capital."),
    Specialist("passport", "PassportKeeper", "Venture Passport", "passport_review", ("artifact.read", "lineage.check", "passport.snapshot"), tuple(x for x in ["home", "research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "academy", "ecosystem", "investor"]), tuple(x for x in ["home", "research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "academy", "ecosystem", "investor"]), EmptyInputs, "Preserve accepted versions and explain evidence, readiness and skill separately."),
]}

# Each node names exact upstream nodes. Feedback creates a new journey, not a cycle in a job DAG.
PIPELINES = {
    "first_evidence": ("Raw idea to first evidence", [("home", []), ("research", ["home"]), ("customer", ["research"]), ("model", ["customer"]), ("experiment", ["model"]), ("passport", ["experiment"])]),
    "pivot": ("Evidence-led pivot", [("home", []), ("research", ["home"]), ("customer", ["research"]), ("competitor", ["research", "customer"]), ("model", ["customer", "competitor"]), ("finance", ["model"]), ("experiment", ["finance", "model"]), ("passport", ["experiment"])]),
    "learning": ("Founder learning journey", [("home", []), ("academy", ["home"]), ("research", ["academy"]), ("customer", ["research"]), ("model", ["customer"]), ("experiment", ["model"]), ("passport", ["experiment"])]),
    "funding": ("Funding preparation", [("home", []), ("research", ["home"]), ("market", ["research"]), ("model", ["market"]), ("finance", ["model"]), ("ecosystem", ["research"]), ("investor", ["finance", "market", "ecosystem"]), ("passport", ["investor"])]),
    "complete": ("All thirteen specialists", [("home", []), ("research", ["home"]), ("market", ["research"]), ("customer", ["market"]), ("competitor", ["research", "customer"]), ("model", ["market", "customer", "competitor"]), ("finance", ["model"]), ("experiment", ["model", "customer", "finance"]), ("simulation", ["finance", "competitor"]), ("academy", ["simulation", "experiment"]), ("ecosystem", ["research"]), ("investor", ["finance", "market", "ecosystem", "experiment"]), ("passport", ["home", "research", "market", "customer", "competitor", "model", "finance", "experiment", "simulation", "academy", "ecosystem", "investor"])])
}

# Journey edges extend the application handoff matrix explicitly, including skill referrals.
# Publish the same allowlist used to create handoffs and admit specialist context.
for _, stages in PIPELINES.values():
    for target, dependencies in stages:
        target_spec = REGISTRY[target]
        REGISTRY[target] = replace(target_spec, receives=tuple(dict.fromkeys((*target_spec.receives, *dependencies))))
        for source in dependencies:
            source_spec = REGISTRY[source]
            REGISTRY[source] = replace(source_spec, sends=tuple(dict.fromkeys((*source_spec.sends, target))))
# SkillCoach's finance exercise reads only an accepted financial artifact.
REGISTRY["academy"] = replace(REGISTRY["academy"], receives=(*REGISTRY["academy"].receives, "finance"))

# Capability contracts select profiles at run time; none names a provider or model.
_REQUIREMENTS = {
    "home": ("guidance", "standard", 8192, False),
    "research": ("synthesis", "high", 32768, True),
    "market": ("reasoning", "standard", 16384, False),
    "customer": ("synthesis", "high", 32768, False),
    "competitor": ("synthesis", "high", 32768, True),
    "model": ("reasoning", "high", 16384, False),
    "finance": ("explanation", "standard", 16384, False),
    "experiment": ("reasoning", "high", 16384, False),
    "simulation": ("explanation", "standard", 8192, False),
    "academy": ("guidance", "standard", 8192, False),
    "ecosystem": ("diligence", "high", 32768, True),
    "investor": ("diligence", "high", 32768, False),
    "passport": ("synthesis", "high", 65536, False),
}
for ident, (task, reasoning, context, tools) in _REQUIREMENTS.items():
    specialist = REGISTRY[ident]
    REGISTRY[ident] = replace(specialist, model_requirements=ModelRequirements(task=task, reasoning=reasoning, min_context_tokens=context, tool_calling=tools, deterministic_operations=specialist.tools))
