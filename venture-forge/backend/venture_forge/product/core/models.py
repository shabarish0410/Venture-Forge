from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, JSON, CheckConstraint, false, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Founder(Base):
    __tablename__ = "founders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100), default="Founder")
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


class Session(Base):
    __tablename__ = "product_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[str] = mapped_column(ForeignKey("founders.id", ondelete="CASCADE"), index=True)
    realm: Mapped[str] = mapped_column(String(16), default="product")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    auth_method: Mapped[str] = mapped_column(String(16), default="password", server_default="password")
    __table_args__ = (CheckConstraint("realm = 'product'", name="session_product_realm"),)


class Venture(Base):
    __tablename__ = "ventures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("founders.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    idea: Mapped[str] = mapped_column(Text)
    customer_segment: Mapped[str] = mapped_column(String(300))
    geography: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(40), default="idea")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("id", "owner_id", name="venture_ownership"),)


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    venture_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    statement: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="unvalidated")
    origin: Mapped[str] = mapped_column(String(24), default="founder_asserted")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reference_code: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "venture_id", "owner_id", name="hypothesis_record_scope"),
        UniqueConstraint("venture_id", "reference_code", name="hypothesis_reference_scope"),
        CheckConstraint("priority IN ('normal','high','critical')", name="hypothesis_priority"),
        ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"], ondelete="CASCADE"),
        CheckConstraint("status = 'unvalidated'", name="foundation_unvalidated_only"),
        CheckConstraint("origin = 'founder_asserted'", name="foundation_founder_origin"),
        CheckConstraint("category IN ('problem','customer','pricing','solution')", name="hypothesis_category"),
    )


class Activity(Base):
    __tablename__ = "activity_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    venture_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"], ondelete="CASCADE"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("founders.id"))
    operation: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("owner_id", "operation", "key", name="idempotency_scope"),)


# Register the additive research tables in the same migration metadata.
from venture_forge.product.research import models as research_models  # noqa: E402,F401
from venture_forge.product.core import workflow_models  # noqa: E402,F401
from venture_forge.product.agents import models as agent_models  # noqa: E402,F401
from venture_forge.product.core import auth_models  # noqa: E402,F401
