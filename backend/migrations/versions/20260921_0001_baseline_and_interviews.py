"""Create the current schema or upgrade the pre-Alembic local schema.

Revision ID: 20260921_0001
Revises:
"""
from alembic import op
from sqlalchemy import inspect

from app.core.database import Base, ensure_local_schema
from app.models import Activity, Application, Candidate, Interview, Job, Resume, Task  # noqa: F401

revision = "20260921_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "applications" not in inspect(bind).get_table_names():
        Base.metadata.create_all(bind)
    else:
        # Converts the former non-versioned schema without discarding local data.
        ensure_local_schema()


def downgrade():
    # Baseline is intentionally forward-only: local business records must not be dropped.
    pass
