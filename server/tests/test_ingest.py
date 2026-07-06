import uuid

from conftest import TEST_API_KEY
from sqlmodel import select

from app.models import LLMCall, Run, Span
from app.pricing import compute_cost

HEADERS = {"X-API-Key": TEST_API_KEY}


def make_run_batch():
    """Synthetic 3-agent run: planner -> (nutrition -> [llm, tool], formatter -> llm)."""
    run_id = str(uuid.uuid4())
    planner = str(uuid.uuid4())
    nutrition = str(uuid.uuid4())
    tool = str(uuid.uuid4())
    formatter = str(uuid.uuid4())
    llm1 = str(uuid.uuid4())
    llm2 = str(uuid.uuid4())
    ids = {
        "run": run_id, "planner": planner, "nutrition": nutrition,
        "tool": tool, "formatter": formatter, "llm1": llm1, "llm2": llm2,
    }
    events = [
        {"type": "run_start", "id": run_id, "project": "fittrack-recipes",
         "name": "generate_recipe", "tags": {"env": "test"},
         "metadata": {"user_tier": "free"}, "started_at": "2026-07-07T10:00:00Z"},
        {"type": "span_start", "id": planner, "run_id": run_id, "parent_span_id": None,
         "name": "planner_agent", "span_type": "agent",
         "input": {"query": "high protein vegetarian dinner"},
         "started_at": "2026-07-07T10:00:00.100Z"},
        {"type": "span_start", "id": nutrition, "run_id": run_id, "parent_span_id": planner,
         "name": "nutrition_agent", "span_type": "agent",
         "started_at": "2026-07-07T10:00:00.120Z"},
        {"type": "llm_call", "id": llm1, "run_id": run_id, "parent_span_id": nutrition,
         "name": "claude_call", "provider": "anthropic", "model": "claude-sonnet-4-6",
         "request_messages": [{"role": "user", "content": "plan macros"}],
         "request_params": {"max_tokens": 1024, "temperature": 0.7},
         "response_content": [{"type": "text", "text": "..."}],
         "finish_reason": "end_turn", "input_tokens": 830, "output_tokens": 412,
         "started_at": "2026-07-07T10:00:00.200Z", "ended_at": "2026-07-07T10:00:01.900Z"},
        {"type": "span_start", "id": tool, "run_id": run_id, "parent_span_id": nutrition,
         "name": "spoonacular_lookup", "span_type": "tool",
         "input": {"query": "lentils"}, "started_at": "2026-07-07T10:00:02.000Z"},
        {"type": "span_end", "id": tool, "status": "completed",
         "output": {"results": 3}, "ended_at": "2026-07-07T10:00:02.250Z"},
        {"type": "span_end", "id": nutrition, "status": "completed",
         "output": {"plan": "..."}, "ended_at": "2026-07-07T10:00:02.300Z"},
        {"type": "span_start", "id": formatter, "run_id": run_id, "parent_span_id": planner,
         "name": "formatter_agent", "span_type": "agent",
         "started_at": "2026-07-07T10:00:02.350Z"},
        {"type": "llm_call", "id": llm2, "run_id": run_id, "parent_span_id": formatter,
         "name": "groq_call", "provider": "groq", "model": "llama-3.3-70b-versatile",
         "request_messages": [{"role": "user", "content": "format the recipe"}],
         "response_content": [{"type": "text", "text": "..."}],
         "finish_reason": "stop", "input_tokens": 1000, "output_tokens": 250,
         "started_at": "2026-07-07T10:00:02.400Z", "ended_at": "2026-07-07T10:00:03.000Z"},
        {"type": "span_end", "id": formatter, "status": "completed",
         "output": {"recipe": "..."}, "ended_at": "2026-07-07T10:00:03.050Z"},
        {"type": "span_end", "id": planner, "status": "completed",
         "output": {"done": True}, "ended_at": "2026-07-07T10:00:03.100Z"},
        {"type": "run_end", "id": run_id, "status": "completed",
         "ended_at": "2026-07-07T10:00:03.200Z"},
    ]
    return ids, events


EXPECTED_COST = compute_cost("claude-sonnet-4-6", 830, 412) + compute_cost(
    "llama-3.3-70b-versatile", 1000, 250
)


def test_ingest_reconstructs_span_tree(client, session, project):
    ids, events = make_run_batch()
    resp = client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
    assert resp.status_code == 202
    assert resp.json() == {"accepted": 12, "rejected": []}

    spans = {str(s.id): s for s in session.exec(select(Span)).all()}
    assert len(spans) == 6

    assert spans[ids["planner"]].parent_span_id is None
    assert str(spans[ids["nutrition"]].parent_span_id) == ids["planner"]
    assert str(spans[ids["tool"]].parent_span_id) == ids["nutrition"]
    assert str(spans[ids["llm1"]].parent_span_id) == ids["nutrition"]
    assert str(spans[ids["formatter"]].parent_span_id) == ids["planner"]
    assert str(spans[ids["llm2"]].parent_span_id) == ids["formatter"]
    assert all(str(s.run_id) == ids["run"] for s in spans.values())

    # ORM relationships reconstruct the same tree
    planner = spans[ids["planner"]]
    assert {str(c.id) for c in planner.children} == {ids["nutrition"], ids["formatter"]}
    assert spans[ids["llm1"]].llm_call.model == "claude-sonnet-4-6"

    # span_end payloads and server-computed latency landed
    tool = spans[ids["tool"]]
    assert tool.status == "completed"
    assert tool.output == {"results": 3}
    assert tool.latency_ms == 250
    assert spans[ids["llm1"]].latency_ms == 1700

    run = session.get(Run, uuid.UUID(ids["run"]))
    assert run.status == "completed"
    assert run.ended_at is not None
    assert run.project_id == project.id
    assert run.metadata_ == {"user_tier": "free"}
    assert run.tags == {"env": "test"}


def test_run_rollups_and_cost(client, session, project):
    ids, events = make_run_batch()
    client.post("/v1/ingest", json={"events": events}, headers=HEADERS)

    run = session.get(Run, uuid.UUID(ids["run"]))
    assert run.total_llm_calls == 2
    assert run.total_input_tokens == 830 + 1000
    assert run.total_output_tokens == 412 + 250
    assert run.total_cost_usd == EXPECTED_COST

    llm1 = session.get(LLMCall, uuid.UUID(ids["llm1"]))
    assert llm1.cost_usd == compute_cost("claude-sonnet-4-6", 830, 412)
    llm2 = session.get(LLMCall, uuid.UUID(ids["llm2"]))
    assert llm2.cost_usd == compute_cost("llama-3.3-70b-versatile", 1000, 250)


def test_idempotent_replay(client, session, project):
    ids, events = make_run_batch()
    first = client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
    second = client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
    assert first.json() == {"accepted": 12, "rejected": []}
    assert second.json() == {"accepted": 12, "rejected": []}

    assert len(session.exec(select(Span)).all()) == 6
    assert len(session.exec(select(LLMCall)).all()) == 2
    assert len(session.exec(select(Run)).all()) == 1

    run = session.get(Run, uuid.UUID(ids["run"]))
    assert run.total_llm_calls == 2
    assert run.total_input_tokens == 1830
    assert run.total_output_tokens == 662
    assert run.total_cost_usd == EXPECTED_COST


def test_malformed_event_rejected_without_failing_batch(client, session, project):
    ids, events = make_run_batch()
    events.insert(3, {"type": "span_start", "id": str(uuid.uuid4())})  # missing required fields
    resp = client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 12
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["index"] == 3
    assert "run_id" in body["rejected"][0]["reason"]

    # everything else still landed
    assert len(session.exec(select(Span)).all()) == 6
    run = session.get(Run, uuid.UUID(ids["run"]))
    assert run.total_llm_calls == 2


def test_unknown_model_rejected(client, session, project):
    ids, events = make_run_batch()
    events[3]["model"] = "gpt-99-mystery"
    resp = client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
    body = resp.json()
    assert body["accepted"] == 11
    assert body["rejected"][0]["id"] == ids["llm1"]
    assert "gpt-99-mystery" in body["rejected"][0]["reason"]

    run = session.get(Run, uuid.UUID(ids["run"]))
    assert run.total_llm_calls == 1  # only the valid llm_call counted
    assert run.total_cost_usd == compute_cost("llama-3.3-70b-versatile", 1000, 250)


def test_client_supplied_cost_and_latency_ignored(client, session, project):
    ids, events = make_run_batch()
    events[3]["cost_usd"] = "999.99"
    events[3]["latency_ms"] = 1
    client.post("/v1/ingest", json={"events": events}, headers=HEADERS)

    llm1 = session.get(LLMCall, uuid.UUID(ids["llm1"]))
    assert llm1.cost_usd == compute_cost("claude-sonnet-4-6", 830, 412)
    assert session.get(Span, uuid.UUID(ids["llm1"])).latency_ms == 1700


def test_auth_required(client, project):
    _, events = make_run_batch()
    missing = client.post("/v1/ingest", json={"events": events})
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"

    wrong = client.post("/v1/ingest", json={"events": events}, headers={"X-API-Key": "nope"})
    assert wrong.status_code == 401


def test_redis_down_does_not_break_ingestion(client, session, project, monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")  # nothing listens there
    ids, events = make_run_batch()
    resp = client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
    assert resp.status_code == 202
    assert resp.json()["accepted"] == 12
    assert session.get(Run, uuid.UUID(ids["run"])).status == "completed"


def test_redis_receives_run_updates(client, project):
    import json
    import time

    import redis

    r = redis.Redis.from_url("redis://localhost:6379/0")
    ids, events = make_run_batch()
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(f"run:{ids['run']}")
    try:
        client.post("/v1/ingest", json={"events": events}, headers=HEADERS)
        messages = []
        deadline = time.time() + 3
        # get_message returns None for ignored subscribe confirmations too,
        # so poll until the deadline rather than stopping at the first None.
        while time.time() < deadline and len(messages) < 12:
            msg = pubsub.get_message(timeout=0.1)
            if msg is not None and msg["type"] == "message":
                messages.append(msg)
        assert len(messages) == 12
        first = json.loads(messages[0]["data"])
        assert first["type"] == "run_start"
        assert first["id"] == ids["run"]
    finally:
        pubsub.close()
        r.close()
