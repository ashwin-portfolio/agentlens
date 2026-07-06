"""SQLModel entities mirroring docs/02-ARCHITECTURE.md §3 (Week 1 subset).

Per D6: payloads (prompts, responses, metadata) are JSONB; anything filtered
or aggregated on is a real column. Eval/prompt/replay tables land in Weeks 6-10.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


def _timestamptz(nullable: bool = False) -> Column:
    return Column(DateTime(timezone=True), nullable=nullable)


class Project(SQLModel, table=True):
    __tablename__ = "project"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    api_key_hash: str
    created_at: datetime = Field(sa_column=_timestamptz())

    runs: list["Run"] = Relationship(back_populates="project")


class Run(SQLModel, table=True):
    __tablename__ = "run"
    __table_args__ = (Index("idx_run_project_started", "project_id", text("started_at DESC")),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="project.id")
    name: str
    status: str = "running"
    metadata_: dict | None = Field(default=None, sa_column=Column("metadata", JSONB))
    tags: dict | None = Field(default=None, sa_column=Column(JSONB))
    started_at: datetime = Field(sa_column=_timestamptz())
    ended_at: datetime | None = Field(default=None, sa_column=_timestamptz(nullable=True))
    total_cost_usd: Decimal = Field(
        default=Decimal("0"), sa_column=Column(Numeric(18, 10), nullable=False)
    )
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_llm_calls: int = 0

    project: Project = Relationship(back_populates="runs")
    spans: list["Span"] = Relationship(back_populates="run")


class Span(SQLModel, table=True):
    __tablename__ = "span"
    __table_args__ = (
        Index("idx_span_run", "run_id", "started_at"),
        Index("idx_span_parent", "parent_span_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_id: UUID = Field(foreign_key="run.id")
    parent_span_id: UUID | None = Field(default=None, foreign_key="span.id")
    name: str
    span_type: str
    status: str = "running"
    input: dict | list | None = Field(default=None, sa_column=Column(JSONB))
    output: dict | list | None = Field(default=None, sa_column=Column(JSONB))
    error: str | None = Field(default=None, sa_column=Column(Text))
    metadata_: dict | None = Field(default=None, sa_column=Column("metadata", JSONB))
    started_at: datetime = Field(sa_column=_timestamptz())
    ended_at: datetime | None = Field(default=None, sa_column=_timestamptz(nullable=True))
    latency_ms: int | None = None

    run: Run = Relationship(back_populates="spans")
    parent: "Span" = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Span.id"},
    )
    children: list["Span"] = Relationship(back_populates="parent")
    llm_call: "LLMCall" = Relationship(back_populates="span")


class LLMCall(SQLModel, table=True):
    __tablename__ = "llm_call"
    __table_args__ = (Index("idx_llm_call_model", "model"),)

    span_id: UUID = Field(foreign_key="span.id", primary_key=True)
    provider: str
    model: str
    request_messages: dict | list | None = Field(default=None, sa_column=Column(JSONB))
    request_params: dict | None = Field(default=None, sa_column=Column(JSONB))
    response_content: dict | list | None = Field(default=None, sa_column=Column(JSONB))
    finish_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Field(
        default=Decimal("0"), sa_column=Column(Numeric(18, 10), nullable=False)
    )

    span: Span = Relationship(back_populates="llm_call")
