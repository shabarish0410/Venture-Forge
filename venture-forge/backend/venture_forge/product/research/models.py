from datetime import date, datetime
from sqlalchemy import String, Text, Integer, Date, DateTime, JSON, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, declared_attr
from venture_forge.product.core.models import Base, uid, now


def reference(column: str, table: str):
    return ForeignKeyConstraint([column, "venture_id", "owner_id"], [f"{table}.id", f"{table}.venture_id", f"{table}.owner_id"])


def ownership(table: str):
    return (
        UniqueConstraint("id", "venture_id", "owner_id", name=f"{table}_record_scope"),
        ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"], ondelete="CASCADE"),
    )


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    venture_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    @declared_attr.directive
    def __table_args__(cls):
        return ownership(cls.__tablename__)


class Source(Record, Base):
    __tablename__ = "sources"
    kind: Mapped[str] = mapped_column(String(30))
    locator: Mapped[str] = mapped_column(String(2000))
    __table_args__ = (*ownership("sources"), CheckConstraint("kind IN ('web','document','founder_observation')", name="source_kind"))


class SourceVersion(Record, Base):
    __tablename__ = "source_versions"
    source_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(300))
    published_on: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    capture_method: Mapped[str] = mapped_column(String(60))
    extraction_version: Mapped[str] = mapped_column(String(40), default="text-v1")
    __table_args__ = (*ownership("source_versions"), reference("source_id", "sources"), UniqueConstraint("source_id", "revision", name="source_revision"))


class EvidenceItem(Record, Base):
    __tablename__ = "evidence_items"
    source_version_id: Mapped[str] = mapped_column(String(36))
    excerpt: Mapped[str] = mapped_column(Text)
    excerpt_start: Mapped[int] = mapped_column(Integer)
    excerpt_end: Mapped[int] = mapped_column(Integer)
    population: Mapped[str] = mapped_column(String(500))
    geography: Mapped[str] = mapped_column(String(300))
    method: Mapped[str] = mapped_column(String(1000))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (*ownership("evidence_items"), reference("source_version_id", "source_versions"), CheckConstraint("excerpt_start >= 0 AND excerpt_end > excerpt_start", name="excerpt_offsets"))


class ResearchRun(Record, Base):
    __tablename__ = "research_runs"
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="ready")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(40))
    analysis_provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40), default="research-v1")
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(400))
    unknowns: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    recommended_next_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    customer_handoff: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (*ownership("research_runs"), reference("hypothesis_id", "hypotheses"), CheckConstraint("status IN ('ready','running','completed','failed')", name="research_status"))


class ResearchQuery(Record, Base):
    __tablename__ = "research_queries"
    run_id: Mapped[str] = mapped_column(String(36))
    query: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    provider_request_id: Mapped[str | None] = mapped_column(String(150))
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (*ownership("research_queries"), reference("run_id", "research_runs"))


class Claim(Record, Base):
    __tablename__ = "claims"
    run_id: Mapped[str | None] = mapped_column(String(36))
    statement: Mapped[str] = mapped_column(Text)
    epistemic_status: Mapped[str] = mapped_column(String(30))
    author_type: Mapped[str] = mapped_column(String(20))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (*ownership("claims"), reference("run_id", "research_runs"), CheckConstraint("epistemic_status IN ('SOURCE_REPORTED','FOUNDER_OBSERVED','UNSUPPORTED')", name="claim_epistemic_status"))


class ClaimEvidenceLink(Record, Base):
    __tablename__ = "claim_evidence_links"
    claim_id: Mapped[str] = mapped_column(String(36))
    evidence_id: Mapped[str] = mapped_column(String(36))
    relation: Mapped[str] = mapped_column(String(24))
    __table_args__ = (*ownership("claim_evidence_links"), reference("claim_id", "claims"), reference("evidence_id", "evidence_items"), CheckConstraint("relation IN ('supports','contradicts','contextualizes')", name="claim_evidence_relation"), UniqueConstraint("claim_id", "evidence_id", name="claim_evidence_pair"))


class HypothesisClaimLink(Record, Base):
    __tablename__ = "hypothesis_claim_links"
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    claim_id: Mapped[str] = mapped_column(String(36))
    relation: Mapped[str] = mapped_column(String(24))
    explanation: Mapped[str] = mapped_column(Text)
    __table_args__ = (*ownership("hypothesis_claim_links"), reference("hypothesis_id", "hypotheses"), reference("claim_id", "claims"), CheckConstraint("relation IN ('supports','contradicts','contextualizes')", name="hypothesis_claim_relation"), UniqueConstraint("hypothesis_id", "claim_id", name="hypothesis_claim_pair"))


class ClaimReview(Record, Base):
    __tablename__ = "claim_reviews"
    claim_id: Mapped[str] = mapped_column(String(36))
    verdict: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str] = mapped_column(Text)
    __table_args__ = (*ownership("claim_reviews"), reference("claim_id", "claims"), CheckConstraint("verdict IN ('accepted','rejected')", name="claim_review_verdict"))


class Derivation(Record, Base):
    __tablename__ = "derivations"
    run_id: Mapped[str | None] = mapped_column(String(36))
    label: Mapped[str] = mapped_column(String(300))
    operation: Mapped[str] = mapped_column(String(24))
    formula_version: Mapped[str] = mapped_column(String(24), default="decimal-v1")
    result: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str | None] = mapped_column(String(3))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (*ownership("derivations"), reference("run_id", "research_runs"), CheckConstraint("operation IN ('sum','difference','ratio','percentage','product')", name="derivation_operation"))


class DerivationInput(Record, Base):
    __tablename__ = "derivation_inputs"
    derivation_id: Mapped[str] = mapped_column(String(36))
    evidence_id: Mapped[str] = mapped_column(String(36))
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(100))
    observed_text: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str | None] = mapped_column(String(3))
    time_basis: Mapped[str] = mapped_column(String(100))
    __table_args__ = (*ownership("derivation_inputs"), reference("derivation_id", "derivations"), reference("evidence_id", "evidence_items"), UniqueConstraint("derivation_id", "position", name="derivation_input_position"))


class Inference(Record, Base):
    __tablename__ = "inferences"
    run_id: Mapped[str | None] = mapped_column(String(36))
    statement: Mapped[str] = mapped_column(Text)
    epistemic_status: Mapped[str] = mapped_column(String(20), default="INFERENCE")
    author_type: Mapped[str] = mapped_column(String(20))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (*ownership("inferences"), reference("run_id", "research_runs"), CheckConstraint("epistemic_status = 'INFERENCE'", name="inference_remains_inference"))


class InferenceBasis(Record, Base):
    __tablename__ = "inference_basis"
    inference_id: Mapped[str] = mapped_column(String(36))
    claim_id: Mapped[str | None] = mapped_column(String(36))
    derivation_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (*ownership("inference_basis"), reference("inference_id", "inferences"), reference("claim_id", "claims"), reference("derivation_id", "derivations"), CheckConstraint("(claim_id IS NOT NULL AND derivation_id IS NULL) OR (claim_id IS NULL AND derivation_id IS NOT NULL)", name="one_inference_basis"))
