from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, JSON, Boolean, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, declared_attr
from .models import Base, uid, now


class Scoped:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    venture_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    @declared_attr.directive
    def __table_args__(cls):
        constraints = [UniqueConstraint("id", "venture_id", "owner_id"), ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"])]
        references = {
            "evidence_receipts": [("hypothesis_id", "hypotheses")],
            "locked_experiments": [("hypothesis_id", "hypotheses")],
            "experiment_observations": [("experiment_id", "locked_experiments"), ("receipt_id", "evidence_receipts")],
            "workflow_runs": [("hypothesis_id", "hypotheses")],
        }
        for column, table in references.get(cls.__tablename__, []):
            constraints.append(ForeignKeyConstraint([column, "venture_id", "owner_id"], [f"{table}.id", f"{table}.venture_id", f"{table}.owner_id"]))
        if cls.__tablename__ == "experiment_observations":
            constraints.extend([UniqueConstraint("experiment_id", "participant_code"), UniqueConstraint("experiment_id", "receipt_id")])
        if cls.__tablename__ == "founder_decisions":
            constraints.append(UniqueConstraint("target_type", "target_id"))
        return tuple(constraints)


class Receipt(Scoped, Base):
    __tablename__ = "evidence_receipts"
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(String(2000))
    content_hash: Mapped[str] = mapped_column(String(64))
    relation: Mapped[str] = mapped_column(String(24))
    limitations: Mapped[str] = mapped_column(Text)
    consent: Mapped[str] = mapped_column(String(50))
    participant_code: Mapped[str | None] = mapped_column(String(60))
    collected_on: Mapped[str] = mapped_column(String(10))
    withdrawn: Mapped[bool] = mapped_column(Boolean, default=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Artifact(Scoped, Base):
    __tablename__ = "tool_artifacts"
    capability: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    venture_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="PROPOSED")
    formula_version: Mapped[str] = mapped_column(String(30), default="rules-v1")


class Experiment(Scoped, Base):
    __tablename__ = "locked_experiments"
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(300))
    protocol: Mapped[dict] = mapped_column(JSON)
    protocol_hash: Mapped[str] = mapped_column(String(64))
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Observation(Scoped, Base):
    __tablename__ = "experiment_observations"
    experiment_id: Mapped[str] = mapped_column(String(36))
    participant_code: Mapped[str] = mapped_column(String(60))
    receipt_id: Mapped[str] = mapped_column(String(36))
    success: Mapped[bool] = mapped_column(Boolean)
    instrument_valid: Mapped[bool] = mapped_column(Boolean)
    deviation: Mapped[str] = mapped_column(Text)


class Decision(Scoped, Base):
    __tablename__ = "founder_decisions"
    target_id: Mapped[str] = mapped_column(String(36))
    target_type: Mapped[str] = mapped_column(String(20))
    choice: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    result_snapshot: Mapped[dict] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)


class Run(Scoped, Base):
    __tablename__ = "workflow_runs"
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    capability: Mapped[str] = mapped_column(String(30))
    objective: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    input_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    proposal: Mapped[dict] = mapped_column(JSON, default=dict)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String(300))
