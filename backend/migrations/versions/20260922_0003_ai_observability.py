"""Add structured AI observability."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0003"
down_revision = "20260921_0002"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "agent_runs" in tables:
        additions = [
            ("provider", sa.String(80)), ("prompt_version", sa.String(40)),
            ("latency_ms", sa.Integer()), ("repair_attempted", sa.Boolean()),
            ("fallback_used", sa.Boolean()), ("error_stage", sa.String(40)),
            ("error_type", sa.String(80)),
        ]
        columns = _columns(bind, "agent_runs")
        for name, column_type in additions:
            if name not in columns:
                op.add_column("agent_runs", sa.Column(name, column_type, nullable=True))
        bind.execute(sa.text("UPDATE agent_runs SET status = 'success' WHERE status = 'succeeded'"))
    if "ai_model_calls" not in tables:
        op.create_table("ai_model_calls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False),
            sa.Column("provider", sa.String(80)), sa.Column("model", sa.String(80), nullable=False),
            sa.Column("call_type", sa.String(20), nullable=False, server_default="primary"),
            sa.Column("request_id", sa.String(120)), sa.Column("prompt_version", sa.String(40)),
            sa.Column("raw_response", sa.Text()), sa.Column("finish_reason", sa.String(40)),
            sa.Column("latency_ms", sa.Integer()), sa.Column("error_message", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ai_model_calls_agent_run_id", "ai_model_calls", ["agent_run_id"])
    if "ai_validation_errors" not in tables:
        op.create_table("ai_validation_errors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False),
            sa.Column("model_call_id", sa.Integer(), sa.ForeignKey("ai_model_calls.id")),
            sa.Column("stage", sa.String(40), nullable=False), sa.Column("error_type", sa.String(80), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=False), sa.Column("parsed_output", sa.JSON()),
            sa.Column("schema_name", sa.String(120)), sa.Column("repair_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ai_validation_errors_agent_run_id", "ai_validation_errors", ["agent_run_id"])
        op.create_index("ix_ai_validation_errors_model_call_id", "ai_validation_errors", ["model_call_id"])


def downgrade():
    op.drop_table("ai_validation_errors")
    op.drop_table("ai_model_calls")
