"""Week 1 tables: project, run, span, llm_call + indexes from ARCHITECTURE §5.

The eval_result/eval_score indexes from §5 belong to tables that land in
Weeks 6-8; they ship with that migration.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("api_key_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(18, 10), nullable=False),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_llm_calls", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "span",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("parent_span_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("span_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input", JSONB(), nullable=True),
        sa.Column("output", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"]),
        sa.ForeignKeyConstraint(["parent_span_id"], ["span.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "llm_call",
        sa.Column("span_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("request_messages", JSONB(), nullable=True),
        sa.Column("request_params", JSONB(), nullable=True),
        sa.Column("response_content", JSONB(), nullable=True),
        sa.Column("finish_reason", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(18, 10), nullable=False),
        sa.ForeignKeyConstraint(["span_id"], ["span.id"]),
        sa.PrimaryKeyConstraint("span_id"),
    )

    op.create_index(
        "idx_run_project_started",
        "run",
        ["project_id", sa.text("started_at DESC")],
    )
    op.create_index("idx_span_run", "span", ["run_id", "started_at"])
    op.create_index("idx_span_parent", "span", ["parent_span_id"])
    op.create_index("idx_llm_call_model", "llm_call", ["model"])


def downgrade() -> None:
    op.drop_index("idx_llm_call_model", table_name="llm_call")
    op.drop_index("idx_span_parent", table_name="span")
    op.drop_index("idx_span_run", table_name="span")
    op.drop_index("idx_run_project_started", table_name="run")
    op.drop_table("llm_call")
    op.drop_table("span")
    op.drop_table("run")
    op.drop_table("project")
