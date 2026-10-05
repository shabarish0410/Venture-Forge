"""Domain output contracts, validated before any proposal can reach founder review."""
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, model_validator
from .registry import FinanceInputs, MarketInputs


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_assistance: dict | None = None


class ConceptMap(Output):
    fields: dict[str, dict[str, str]]
    mission: dict[str, str]


class ResearchMemo(Output):
    question: str
    source_registry: list[dict]
    claim_ledger: list[dict]
    contradictions: list[str]
    refresh_source_ids: list[str]


class MarketDefinition(Output):
    definition: dict[str, str]
    drivers: MarketInputs
    sizing: dict


class CustomerSynthesis(Output):
    invited: int
    interviewed: int
    nonresponse: int
    observation_ledger: list[dict]
    contrary_receipts: list[str]
    interview_guide: list[str]
    purchase_evidence: Literal["unknown"]


class AlternativeMap(Output):
    alternative_map: list[dict]
    status_quo_included: bool
    switching_test: str


class BusinessModel(Output):
    fields: dict[str, str | Decimal]
    model_options: list[dict[str, str]]
    pricing_test: str


class FinancialModel(Output):
    drivers: FinanceInputs
    financials: dict
    actuals_status: str

    @model_validator(mode="after")
    def authoritative_figures(self):
        from venture_forge.product.core.tools import calculate
        if self.financials != calculate("finance", self.drivers):
            raise ValueError("Financial figures must match the deterministic calculation from their drivers")
        return self


class DraftExperiment(Output):
    protocol_draft: dict
    hypothesis: str
    mvp_boundary: str
    non_goals: list[str]
    locked: Literal[False]


class LockedExperimentReview(Output):
    locked_results: list[dict]
    protocol_edit_allowed: Literal[False]


class SimulationResult(Output):
    source_finance_id: str
    starting_drivers: FinanceInputs
    decisions: dict
    formula_version: str
    baseline: dict
    round: dict
    status: Literal["SIMULATED"]
    reality_gap: str


class MissingSimulation(Output):
    status: Literal["SIMULATED"]
    rounds: list


class LearningMission(Output):
    topic: str
    lesson_title: str
    lesson: str
    applied_exercise: str
    answer: str
    hints_used: int
    assessment: str
    feedback: str
    return_to: str
    transfer_status: str


class OpportunityShortlist(Output):
    shortlist: list[dict]
    excluded_expired: int
    ranking: str
    application_checklist: list[str]


class FundingReadiness(Output):
    funding_milestone: str
    amount_inr: Decimal | None
    readiness_gaps: list[str]
    reviewed_figures: list[dict]
    negative_experiments: list[str]
    capital_alternatives: list[str]
    outreach_enabled: Literal[False]


class PassportReview(Output):
    accepted_artifact_ids: list[str]
    active_evidence_ids: list[str]
    readiness: dict
    evidence_confidence: dict
    founder_capability: dict
    versions: list[dict[str, str]]


OUTPUTS = {"home": ConceptMap, "research": ResearchMemo, "market": MarketDefinition, "customer": CustomerSynthesis, "competitor": AlternativeMap, "model": BusinessModel, "finance": FinancialModel, "academy": LearningMission, "ecosystem": OpportunityShortlist, "investor": FundingReadiness, "passport": PassportReview}


def validate_data(agent, data):
    contract = OUTPUTS.get(agent)
    if agent == "experiment": contract = LockedExperimentReview if "locked_results" in data else DraftExperiment
    if agent == "simulation": contract = SimulationResult if "source_finance_id" in data else MissingSimulation
    contract.model_validate(data)
    if "model_assistance" in data:
        from .schemas import ModelDraft
        assistance = dict(data["model_assistance"])
        if assistance.pop("status") != "MODEL_INFERENCE": raise ValueError("Invalid model assistance label")
        ModelDraft.model_validate(assistance)
