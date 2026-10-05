"""Add specialist execution, pipeline stages and durable handoffs."""
from alembic import op
from venture_forge.product.core.models import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    for name in ["agent_pipelines", "pipeline_stages", "specialist_runs", "specialist_handoffs"]:
        Base.metadata.tables[name].create(op.get_bind(), checkfirst=True)


def downgrade():
    for name in ["specialist_handoffs", "specialist_runs", "pipeline_stages", "agent_pipelines"]:
        Base.metadata.tables[name].drop(op.get_bind(), checkfirst=True)
