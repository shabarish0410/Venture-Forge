"""Add Google/GitHub identities and expiring OAuth state; preserve founder data."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("oauth_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("founder_id", sa.String(36), sa.ForeignKey("founders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="oauth_provider_subject"),
        sa.UniqueConstraint("founder_id", "provider", name="oauth_founder_provider"),
        sa.CheckConstraint("provider IN ('google','github')", name="oauth_identity_provider"))
    op.create_index("ix_oauth_identities_founder_id", "oauth_identities", ["founder_id"])
    op.create_table("oauth_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("founder_id", sa.String(36), sa.ForeignKey("founders.id", ondelete="CASCADE")),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("product_sessions.token_hash", ondelete="CASCADE")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google','github')", name="oauth_attempt_provider"),
        sa.CheckConstraint("(mode = 'sign_in' AND founder_id IS NULL AND session_hash IS NULL) OR (mode = 'connect' AND founder_id IS NOT NULL AND session_hash IS NOT NULL)", name="oauth_attempt_mode_scope"))
    op.create_index("ix_oauth_attempts_expires_at", "oauth_attempts", ["expires_at"])


def downgrade():
    op.drop_table("oauth_attempts")
    op.drop_table("oauth_identities")
