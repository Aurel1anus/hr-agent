"""Prevent duplicate active AI runs per task scope."""
from alembic import op

revision = "20260922_0004"
down_revision = "20260922_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_active_scope
        ON agent_runs (agent_type, COALESCE(application_id, -1), COALESCE(job_id, -1))
        WHERE status = 'running'""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_agent_runs_active_scope")
