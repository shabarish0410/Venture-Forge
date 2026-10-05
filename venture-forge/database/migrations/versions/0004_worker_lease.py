"""Track claimed specialist work for bounded interruption recovery."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Migration 0003 creates tables from current metadata on a fresh install.
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("specialist_runs")}
    if "started_at" not in columns:
        op.add_column("specialist_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("specialist_runs") as batch:
        batch.drop_column("started_at")
