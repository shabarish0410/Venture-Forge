"""Extend the existing founder account for public authentication."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("founders") as batch:
        batch.alter_column("password_hash", existing_type=sa.Text(), nullable=True)
        batch.add_column(sa.Column("avatar_url", sa.String(2048)))
        batch.add_column(sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.execute(sa.text("UPDATE founders SET onboarding_completed = true WHERE EXISTS (SELECT 1 FROM ventures WHERE ventures.owner_id = founders.id)"))
    with op.batch_alter_table("product_sessions") as batch:
        batch.add_column(sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("auth_method", sa.String(16), nullable=False, server_default="password"))
    # Do not grant legacy sessions a new recent-authentication window.
    op.execute(sa.text("UPDATE product_sessions SET authenticated_at = (SELECT created_at FROM founders WHERE founders.id = product_sessions.founder_id)"))
    with op.batch_alter_table("product_sessions") as batch:
        batch.alter_column("authenticated_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    with op.batch_alter_table("oauth_identities") as batch:
        batch.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("display_name", sa.String(100)))
        batch.add_column(sa.Column("avatar_url", sa.String(2048)))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True)))
    # Only transient, in-flight authorizations must restart after this upgrade.
    op.execute(sa.text("DELETE FROM oauth_attempts"))
    with op.batch_alter_table("oauth_attempts") as batch:
        batch.add_column(sa.Column("redirect_uri", sa.String(2048), nullable=False))
        batch.drop_constraint("oauth_attempt_mode_scope", type_="check")
        batch.create_check_constraint("oauth_attempt_mode_scope", "(mode = 'sign_in' AND founder_id IS NULL) OR (mode = 'connect' AND founder_id IS NOT NULL AND session_hash IS NOT NULL)")
    op.create_table("auth_rate_limits", sa.Column("key", sa.String(64), primary_key=True), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])


def downgrade():
    op.drop_table("auth_rate_limits")
    op.execute(sa.text("DELETE FROM oauth_attempts"))
    with op.batch_alter_table("oauth_attempts") as batch:
        batch.drop_constraint("oauth_attempt_mode_scope", type_="check")
        batch.create_check_constraint("oauth_attempt_mode_scope", "(mode = 'sign_in' AND founder_id IS NULL AND session_hash IS NULL) OR (mode = 'connect' AND founder_id IS NOT NULL AND session_hash IS NOT NULL)")
        batch.drop_column("redirect_uri")
    with op.batch_alter_table("oauth_identities") as batch:
        for column in ("email_verified", "display_name", "avatar_url", "last_login_at"):
            batch.drop_column(column)
    with op.batch_alter_table("product_sessions") as batch:
        batch.drop_column("authenticated_at")
        batch.drop_column("auth_method")
    # The previous schema requires a hash. An invalid marker cannot authenticate.
    op.execute(sa.text("UPDATE founders SET password_hash = 'oauth-only-no-password' WHERE password_hash IS NULL"))
    with op.batch_alter_table("founders") as batch:
        batch.alter_column("password_hash", existing_type=sa.Text(), nullable=False)
        for column in ("avatar_url", "onboarding_completed", "is_active", "last_login_at"):
            batch.drop_column(column)
