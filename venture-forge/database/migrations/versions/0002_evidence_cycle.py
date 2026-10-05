"""Add the existing research metadata and the tool-first evidence cycle."""
from alembic import op
import sqlalchemy as sa
from venture_forge.product.core.models import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hypotheses", sa.Column("reference_code", sa.String(40), nullable=True))
    op.add_column("hypotheses", sa.Column("priority", sa.String(16), nullable=False, server_default="normal"))
    with op.batch_alter_table("hypotheses") as batch:
        batch.create_unique_constraint("hypothesis_record_scope", ["id", "venture_id", "owner_id"])
        batch.create_unique_constraint("hypothesis_reference_scope", ["venture_id", "reference_code"])
        batch.create_check_constraint("hypothesis_priority", "priority IN ('normal','high','critical')")
    later_tables = {"agent_pipelines", "pipeline_stages", "specialist_runs", "specialist_handoffs", "oauth_identities", "oauth_attempts", "auth_rate_limits"}
    # Later revisions own these tables, including on a completely fresh install.
    Base.metadata.create_all(op.get_bind(), tables=[t for t in Base.metadata.sorted_tables if t.name not in later_tables], checkfirst=True)


def downgrade():
    base = {"founders", "product_sessions", "ventures", "hypotheses", "activity_events", "idempotency_records"}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in base: table.drop(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("hypotheses") as batch:
        batch.drop_constraint("hypothesis_priority", type_="check")
        batch.drop_constraint("hypothesis_reference_scope", type_="unique")
        batch.drop_constraint("hypothesis_record_scope", type_="unique")
        batch.drop_column("priority")
        batch.drop_column("reference_code")
