"""Provider identities and short-lived, browser-bound OAuth attempts."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, now, uid


class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    founder_id: Mapped[str] = mapped_column(ForeignKey("founders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(254))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    display_name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="oauth_provider_subject"),
        UniqueConstraint("founder_id", "provider", name="oauth_founder_provider"),
        CheckConstraint("provider IN ('google','github')", name="oauth_identity_provider"),
    )


class OAuthAttempt(Base):
    __tablename__ = "oauth_attempts"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    browser_hash: Mapped[str] = mapped_column(String(64))
    code_verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(128))
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    mode: Mapped[str] = mapped_column(String(16))
    founder_id: Mapped[str | None] = mapped_column(ForeignKey("founders.id", ondelete="CASCADE"))
    session_hash: Mapped[str | None] = mapped_column(ForeignKey("product_sessions.token_hash", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        CheckConstraint("provider IN ('google','github')", name="oauth_attempt_provider"),
        CheckConstraint("(mode = 'sign_in' AND founder_id IS NULL) OR (mode = 'connect' AND founder_id IS NOT NULL AND session_hash IS NOT NULL)", name="oauth_attempt_mode_scope"),
    )


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
