"""Product foundation. Company records live in a separate database."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("founders", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(254), nullable=False, unique=True), sa.Column("name", sa.String(100), nullable=False), sa.Column("password_hash", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("product_sessions", sa.Column("token_hash", sa.String(64), primary_key=True), sa.Column("founder_id", sa.String(36), sa.ForeignKey("founders.id", ondelete="CASCADE"), nullable=False), sa.Column("realm", sa.String(16), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("realm = 'product'", name="session_product_realm"))
    op.create_index("ix_product_sessions_founder_id", "product_sessions", ["founder_id"])
    op.create_table("ventures", sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("founders.id"), nullable=False, unique=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("idea", sa.Text(), nullable=False), sa.Column("customer_segment", sa.String(300), nullable=False), sa.Column("geography", sa.String(120), nullable=False), sa.Column("stage", sa.String(40), nullable=False), sa.Column("revision", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("id", "owner_id", name="venture_ownership"))
    op.create_table("hypotheses", sa.Column("id", sa.String(36), primary_key=True), sa.Column("venture_id", sa.String(36), nullable=False), sa.Column("owner_id", sa.String(36), nullable=False), sa.Column("statement", sa.Text(), nullable=False), sa.Column("category", sa.String(24), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("origin", sa.String(24), nullable=False), sa.Column("revision", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"], ondelete="CASCADE"), sa.CheckConstraint("status = 'unvalidated'", name="foundation_unvalidated_only"), sa.CheckConstraint("origin = 'founder_asserted'", name="foundation_founder_origin"), sa.CheckConstraint("category IN ('problem','customer','pricing','solution')", name="hypothesis_category"))
    op.create_index("ix_hypotheses_venture_id", "hypotheses", ["venture_id"])
    op.create_table("activity_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("venture_id", sa.String(36), nullable=False), sa.Column("owner_id", sa.String(36), nullable=False), sa.Column("event_type", sa.String(60), nullable=False), sa.Column("description", sa.String(300), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["venture_id", "owner_id"], ["ventures.id", "ventures.owner_id"], ondelete="CASCADE"))
    op.create_index("ix_activity_events_venture_id", "activity_events", ["venture_id"])
    op.create_table("idempotency_records", sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("founders.id"), nullable=False), sa.Column("operation", sa.String(100), nullable=False), sa.Column("key", sa.String(100), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("response", sa.JSON(), nullable=False), sa.UniqueConstraint("owner_id", "operation", "key", name="idempotency_scope"))


def downgrade():
    for table in ["idempotency_records", "activity_events", "hypotheses", "ventures", "product_sessions", "founders"]:
        op.drop_table(table)
