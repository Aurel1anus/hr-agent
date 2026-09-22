"""Add Recruitment Agent MVP persistence."""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0002"
down_revision = "20260921_0001"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "jobs" in tables and "jd_text" not in {c["name"] for c in inspector.get_columns("jobs")}: op.add_column("jobs", sa.Column("jd_text", sa.Text(), nullable=True))
    if "resumes" in tables and "extracted_text" not in {c["name"] for c in inspector.get_columns("resumes")}: op.add_column("resumes", sa.Column("extracted_text", sa.Text(), nullable=True))
    if all(name in tables for name in ("job_requirement_profiles", "resume_assessments", "memories", "agent_runs", "agent_tool_calls")):
        return
    op.create_table("job_requirement_profiles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False), sa.Column("revision", sa.Integer(), nullable=False, server_default="1"), sa.Column("raw_jd", sa.Text()), sa.Column("raw_notes", sa.Text()), sa.Column("must_have_json", sa.JSON()), sa.Column("preferred_json", sa.JSON()), sa.Column("skills_json", sa.JSON()), sa.Column("soft_skills_json", sa.JSON()), sa.Column("negative_signals_json", sa.JSON()), sa.Column("verification_questions_json", sa.JSON()), sa.Column("ai_summary", sa.Text()), sa.Column("status", sa.String(20), nullable=False, server_default="draft"), sa.Column("confirmed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("resume_assessments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False), sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False), sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False), sa.Column("requirement_profile_id", sa.Integer(), sa.ForeignKey("job_requirement_profiles.id"), nullable=False), sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id")), sa.Column("recommendation", sa.String(30), nullable=False), sa.Column("overall_score", sa.Integer(), nullable=False), sa.Column("strengths_json", sa.JSON()), sa.Column("gaps_json", sa.JSON()), sa.Column("risks_json", sa.JSON()), sa.Column("missing_information_json", sa.JSON()), sa.Column("verification_questions_json", sa.JSON()), sa.Column("summary", sa.Text(), nullable=False), sa.Column("model_name", sa.String(80), nullable=False), sa.Column("prompt_version", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("memories", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("entity_type", sa.String(30), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False), sa.Column("memory_type", sa.String(50), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("source_type", sa.String(40), nullable=False), sa.Column("source_id", sa.Integer()), sa.Column("importance", sa.Integer(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("valid_from", sa.DateTime()), sa.Column("valid_until", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("deleted_at", sa.DateTime()))
    op.create_table("agent_runs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("agent_type", sa.String(40), nullable=False), sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id")), sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id")), sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id")), sa.Column("input_json", sa.JSON()), sa.Column("output_json", sa.JSON()), sa.Column("model_name", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()))
    op.create_table("agent_tool_calls", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=False), sa.Column("tool_name", sa.String(80), nullable=False), sa.Column("arguments_json", sa.JSON(), nullable=False), sa.Column("result_json", sa.JSON()), sa.Column("risk_level", sa.String(20), nullable=False), sa.Column("requires_approval", sa.Boolean(), nullable=False), sa.Column("approval_status", sa.String(30), nullable=False), sa.Column("approved_at", sa.DateTime()), sa.Column("status", sa.String(20), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(), nullable=False))

def downgrade():
    for name in ("agent_tool_calls", "agent_runs", "memories", "resume_assessments", "job_requirement_profiles"):
        op.drop_table(name)
    op.drop_column("resumes", "extracted_text")
    op.drop_column("jobs", "jd_text")
