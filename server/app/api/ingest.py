"""POST /v1/ingest per docs/03-API-SPEC.md §1.

Idempotency: run_start/span_start/llm_call insert with ON CONFLICT DO NOTHING
on the event id; run rollups increment only when the llm_call row was actually
inserted, so SDK retries never double-count. span_end/run_end are plain updates
(replaying them writes the same values).
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import get_session
from app.models import LLMCall, Project, Run, Span
from app.pricing import UnknownModelError, compute_cost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


class RunStartEvent(BaseModel):
    type: Literal["run_start"]
    id: UUID
    project: str
    name: str
    tags: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    started_at: AwareDatetime


class SpanStartEvent(BaseModel):
    type: Literal["span_start"]
    id: UUID
    run_id: UUID
    parent_span_id: UUID | None = None
    name: str
    span_type: str
    input: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, Any] | None = None
    started_at: AwareDatetime


class SpanEndEvent(BaseModel):
    type: Literal["span_end"]
    id: UUID
    status: str
    output: dict[str, Any] | list[Any] | None = None
    error: str | None = None
    ended_at: AwareDatetime


class LLMCallEvent(BaseModel):
    type: Literal["llm_call"]
    id: UUID
    run_id: UUID
    parent_span_id: UUID | None = None
    name: str
    provider: str
    model: str
    request_messages: list[Any] | dict[str, Any] | None = None
    request_params: dict[str, Any] | None = None
    response_content: list[Any] | dict[str, Any] | None = None
    finish_reason: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None


class RunEndEvent(BaseModel):
    type: Literal["run_end"]
    id: UUID
    status: str
    ended_at: AwareDatetime


IngestEvent = Annotated[
    RunStartEvent | SpanStartEvent | SpanEndEvent | LLMCallEvent | RunEndEvent,
    Field(discriminator="type"),
]
_event_adapter: TypeAdapter[IngestEvent] = TypeAdapter(IngestEvent)


class IngestBody(BaseModel):
    # Raw dicts, validated one at a time: one malformed event must not 422 the batch.
    events: list[dict[str, Any]]


class RejectedEvent(BaseModel):
    index: int
    id: str | None = None
    reason: str


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


class _RejectEvent(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def _latency_ms(started_at: datetime, ended_at: datetime | None) -> int | None:
    if ended_at is None:
        return None
    return int((ended_at - started_at).total_seconds() * 1000)


def _handle_run_start(session: Session, event: RunStartEvent, project: Project) -> UUID:
    session.execute(
        pg_insert(Run.__table__)
        .values(
            id=event.id,
            project_id=project.id,
            name=event.name,
            status="running",
            metadata=event.metadata,
            tags=event.tags,
            started_at=event.started_at,
            total_cost_usd=0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_llm_calls=0,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    return event.id


def _handle_span_start(session: Session, event: SpanStartEvent) -> UUID:
    session.execute(
        pg_insert(Span.__table__)
        .values(
            id=event.id,
            run_id=event.run_id,
            parent_span_id=event.parent_span_id,
            name=event.name,
            span_type=event.span_type,
            status="running",
            input=event.input,
            metadata=event.metadata,
            started_at=event.started_at,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    return event.run_id


def _handle_span_end(session: Session, event: SpanEndEvent) -> UUID:
    span = session.get(Span, event.id)
    if span is None:
        raise _RejectEvent(f"span {event.id} not found for span_end")
    session.execute(
        update(Span)
        .where(Span.id == event.id)
        .values(
            status=event.status,
            output=event.output,
            error=event.error,
            ended_at=event.ended_at,
            latency_ms=_latency_ms(span.started_at, event.ended_at),
        )
    )
    return span.run_id


def _handle_llm_call(session: Session, event: LLMCallEvent) -> UUID:
    try:
        cost = compute_cost(event.model, event.input_tokens, event.output_tokens)
    except UnknownModelError as exc:
        raise _RejectEvent(str(exc)) from None

    status = "completed" if event.ended_at is not None else "running"
    result = session.execute(
        pg_insert(Span.__table__)
        .values(
            id=event.id,
            run_id=event.run_id,
            parent_span_id=event.parent_span_id,
            name=event.name,
            span_type="llm",
            status=status,
            started_at=event.started_at,
            ended_at=event.ended_at,
            latency_ms=_latency_ms(event.started_at, event.ended_at),
        )
        .on_conflict_do_nothing(index_elements=["id"])
        # rowcount is unreliable here (-1 with psycopg3); RETURNING tells us
        # definitively whether this event id was newly inserted.
        .returning(Span.__table__.c.id)
    )
    if result.first() is None:  # already ingested: idempotent no-op, don't re-roll-up
        return event.run_id

    session.execute(
        pg_insert(LLMCall.__table__).values(
            span_id=event.id,
            provider=event.provider,
            model=event.model,
            request_messages=event.request_messages,
            request_params=event.request_params,
            response_content=event.response_content,
            finish_reason=event.finish_reason,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            cost_usd=cost,
        )
    )
    session.execute(
        update(Run)
        .where(Run.id == event.run_id)
        .values(
            total_cost_usd=Run.total_cost_usd + cost,
            total_input_tokens=Run.total_input_tokens + event.input_tokens,
            total_output_tokens=Run.total_output_tokens + event.output_tokens,
            total_llm_calls=Run.total_llm_calls + 1,
        )
    )
    return event.run_id


def _handle_run_end(session: Session, event: RunEndEvent) -> UUID:
    if session.get(Run, event.id) is None:
        raise _RejectEvent(f"run {event.id} not found for run_end")
    session.execute(
        update(Run)
        .where(Run.id == event.id)
        .values(status=event.status, ended_at=event.ended_at)
    )
    return event.id


def _publish_events(published: list[tuple[UUID, dict[str, Any]]]) -> None:
    # Live-view fanout only (F2); ingestion must never fail because Redis is down (D1).
    if not published:
        return
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        try:
            for run_id, payload in published:
                client.publish(f"run:{run_id}", json.dumps(payload))
        finally:
            client.close()
    except redis.RedisError as exc:
        logger.warning("Redis publish failed, continuing without live updates: %s", exc)


@router.post("/ingest", status_code=202)
def ingest(
    body: IngestBody,
    session: Annotated[Session, Depends(get_session)],
    x_api_key: Annotated[str | None, Header()] = None,
):
    if x_api_key is None:
        return _error(401, "unauthorized", "Missing X-API-Key header")
    project = session.exec(
        select(Project).where(Project.api_key_hash == hash_api_key(x_api_key))
    ).first()
    if project is None:
        return _error(401, "unauthorized", "Invalid API key")

    accepted = 0
    rejected: list[RejectedEvent] = []
    published: list[tuple[UUID, dict[str, Any]]] = []

    for index, raw in enumerate(body.events):
        raw_id = raw.get("id") if isinstance(raw.get("id"), str) else None
        try:
            event = _event_adapter.validate_python(raw)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(part) for part in first["loc"])
            rejected.append(
                RejectedEvent(index=index, id=raw_id, reason=f"{loc}: {first['msg']}")
            )
            continue

        try:
            if isinstance(event, RunStartEvent):
                run_id = _handle_run_start(session, event, project)
            elif isinstance(event, SpanStartEvent):
                run_id = _handle_span_start(session, event)
            elif isinstance(event, SpanEndEvent):
                run_id = _handle_span_end(session, event)
            elif isinstance(event, LLMCallEvent):
                run_id = _handle_llm_call(session, event)
            else:
                run_id = _handle_run_end(session, event)
            # Commit per event so one bad event (e.g. FK violation) can't poison the batch.
            session.commit()
        except _RejectEvent as exc:
            session.rollback()
            rejected.append(RejectedEvent(index=index, id=str(event.id), reason=exc.reason))
            continue
        except IntegrityError as exc:
            session.rollback()
            reason = f"constraint violation: {exc.orig}"
            rejected.append(RejectedEvent(index=index, id=str(event.id), reason=reason))
            continue

        accepted += 1
        published.append((run_id, event.model_dump(mode="json")))

    _publish_events(published)

    return {"accepted": accepted, "rejected": [r.model_dump() for r in rejected]}
