from datetime import datetime
from sqlalchemy import String, Text, JSON, Integer, Float, DateTime, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from venture_forge.product.core.models import Base
from venture_forge.product.core.workflow_models import Scoped


class Pipeline(Scoped, Base):
    __tablename__ = "agent_pipelines"
    template: Mapped[str] = mapped_column(String(30))
    objective: Mapped[str] = mapped_column(Text)
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    __table_args__ = (
        UniqueConstraint("id", "venture_id", "owner_id"),
        ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"]),
        ForeignKeyConstraint(["hypothesis_id", "venture_id", "owner_id"], ["hypotheses.id", "hypotheses.venture_id", "hypotheses.owner_id"]),
    )


class Stage(Scoped, Base):
    __tablename__ = "pipeline_stages"
    pipeline_id: Mapped[str] = mapped_column(String(36))
    agent_id: Mapped[str] = mapped_column(String(30))
    position: Mapped[int] = mapped_column(Integer)
    dependencies: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="WAITING")
    run_id: Mapped[str | None] = mapped_column(String(36))
    artifact_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (
        UniqueConstraint("id", "venture_id", "owner_id"), UniqueConstraint("pipeline_id", "agent_id"),
        ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"]),
        ForeignKeyConstraint(["pipeline_id", "venture_id", "owner_id"], ["agent_pipelines.id", "agent_pipelines.venture_id", "agent_pipelines.owner_id"]),
    )


class AgentRun(Scoped, Base):
    __tablename__ = "specialist_runs"
    agent_id: Mapped[str] = mapped_column(String(30))
    objective: Mapped[str] = mapped_column(Text)
    hypothesis_id: Mapped[str] = mapped_column(String(36))
    stage_id: Mapped[str | None] = mapped_column(String(36))
    request: Mapped[dict] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    fingerprints: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    result_hash: Mapped[str | None] = mapped_column(String(64))
    trace: Mapped[list] = mapped_column(JSON, default=list)
    cost_inr: Mapped[float] = mapped_column(Float, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    artifact_id: Mapped[str | None] = mapped_column(String(36))
    input_revision: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "venture_id", "owner_id"),
        ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"]),
        ForeignKeyConstraint(["hypothesis_id", "venture_id", "owner_id"], ["hypotheses.id", "hypotheses.venture_id", "hypotheses.owner_id"]),
        ForeignKeyConstraint(["stage_id", "venture_id", "owner_id"], ["pipeline_stages.id", "pipeline_stages.venture_id", "pipeline_stages.owner_id"]),
    )


class Handoff(Scoped, Base):
    __tablename__ = "specialist_handoffs"
    from_run_id: Mapped[str] = mapped_column(String(36))
    to_agent_id: Mapped[str] = mapped_column(String(30))
    artifact_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="AVAILABLE")
    __table_args__ = (
        UniqueConstraint("id", "venture_id", "owner_id"), UniqueConstraint("from_run_id", "to_agent_id"),
        ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"]),
        ForeignKeyConstraint(["from_run_id", "venture_id", "owner_id"], ["specialist_runs.id", "specialist_runs.venture_id", "specialist_runs.owner_id"]),
        ForeignKeyConstraint(["artifact_id", "venture_id", "owner_id"], ["tool_artifacts.id", "tool_artifacts.venture_id", "tool_artifacts.owner_id"]),
    )
