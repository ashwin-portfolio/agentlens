# AgentLens — API Specification (V1)

Base URL: `/v1` · Auth: `X-API-Key` header (single static key per project in V1 — no user auth).
All timestamps ISO-8601 UTC. All IDs UUIDv4 (client-generated for ingest, server-generated elsewhere).

---

## 1. Ingestion

### POST /v1/ingest
Batched events from the SDK. Idempotent on event `id` (upsert) so SDK retries are safe.

```json
{
  "events": [
    {
      "type": "run_start",
      "id": "run-uuid",
      "project": "fittrack-recipes",
      "name": "generate_recipe",
      "tags": {"env": "prod"},
      "metadata": {"user_tier": "free"},
      "started_at": "2026-07-07T10:00:00Z"
    },
    {
      "type": "span_start",
      "id": "span-uuid",
      "run_id": "run-uuid",
      "parent_span_id": null,
      "name": "nutrition_agent",
      "span_type": "agent",
      "input": {"query": "high protein vegetarian dinner"},
      "started_at": "2026-07-07T10:00:00.120Z"
    },
    {
      "type": "span_end",
      "id": "span-uuid",
      "status": "completed",
      "output": {"plan": "..."},
      "ended_at": "2026-07-07T10:00:02.300Z"
    },
    {
      "type": "llm_call",
      "id": "llmspan-uuid",
      "run_id": "run-uuid",
      "parent_span_id": "span-uuid",
      "name": "claude_call",
      "provider": "anthropic",
      "model": "claude-sonnet-4-6",
      "request_messages": [{"role": "user", "content": "..."}],
      "request_params": {"max_tokens": 1024, "temperature": 0.7},
      "response_content": [{"type": "text", "text": "..."}],
      "finish_reason": "end_turn",
      "input_tokens": 830,
      "output_tokens": 412,
      "started_at": "2026-07-07T10:00:00.200Z",
      "ended_at": "2026-07-07T10:00:01.900Z"
    },
    {
      "type": "run_end",
      "id": "run-uuid",
      "status": "completed",
      "ended_at": "2026-07-07T10:00:02.500Z"
    }
  ]
}
```

**Response 202:** `{"accepted": 5, "rejected": []}`
Server computes `latency_ms` and `cost_usd`, updates run rollups
(total tokens/cost/calls), publishes run updates to Redis channel `run:{id}`.

---

## 2. Runs & Traces

### GET /v1/runs
Query params: `project`, `status`, `tag`, `model`, `from`, `to`, `limit` (default 50), `cursor`.
Returns run summaries (rollup fields included), newest first.

### GET /v1/runs/{run_id}
Full run header + rollups.

### GET /v1/runs/{run_id}/tree
The complete span tree, nested:

```json
{
  "run": {"id": "...", "name": "generate_recipe", "status": "completed",
           "total_cost_usd": 0.0231, "total_input_tokens": 1830, "total_output_tokens": 912},
  "spans": [
    {
      "id": "...", "name": "nutrition_agent", "span_type": "agent",
      "latency_ms": 2180, "status": "completed",
      "children": [
        {"id": "...", "name": "claude_call", "span_type": "llm",
         "latency_ms": 1700, "cost_usd": 0.0087,
         "llm": {"model": "claude-sonnet-4-6", "input_tokens": 830, "output_tokens": 412},
         "children": []}
      ]
    }
  ]
}
```

### GET /v1/spans/{span_id}
Full span detail including LLM payloads (prompt messages, response, params).

### GET /v1/runs/live/{run_id}  (SSE)
Server-sent events stream backed by Redis pub/sub; emits span_start/span_end/run_end
events for in-progress runs.

---

## 3. Analytics

### GET /v1/analytics/costs
Params: `project`, `group_by` = `day|model|run_name|agent`, `from`, `to`.

```json
{"group_by": "model", "rows": [
  {"key": "claude-sonnet-4-6", "cost_usd": 12.41, "input_tokens": 2411000,
   "output_tokens": 890000, "calls": 1841, "avg_latency_ms": 1620}
]}
```

### GET /v1/analytics/latency
Same grouping; returns p50/p95/p99 latency per group.

---

## 4. Evaluation

### POST /v1/datasets · GET /v1/datasets · POST /v1/datasets/{id}/cases (bulk)
CRUD for datasets and test cases. Bulk case upload accepts a JSON array.

### POST /v1/rubrics
```json
{
  "name": "dietary_compliance",
  "judge_model": "claude-sonnet-4-6",
  "min_score": 1, "max_score": 5,
  "judge_prompt_template": "You are grading a recipe recommendation.\nUser requirements: {input}\nRecipe produced: {output}\nExpected properties: {expected}\n\nScore 1-5 for dietary compliance...\nRespond ONLY as JSON: {\"score\": <int>, \"reasoning\": \"...\"}"
}
```

### POST /v1/eval-runs
Two modes:

**Mode A — score stored outputs** (outputs produced by the SDK/user code beforehand):
```json
{"dataset_id": "...", "name": "prompt_v2_sonnet", "rubric_ids": ["...", "..."],
 "outputs": [{"test_case_id": "...", "output": {...}, "latency_ms": 1400, "cost_usd": 0.004}]}
```

**Mode B — server-executed** (V1 supports a single-prompt target):
```json
{"dataset_id": "...", "name": "prompt_v2_haiku", "rubric_ids": ["..."],
 "target": {"prompt_version_id": "...", "model": "claude-haiku-4-5-20251001"}}
```
Server renders the prompt template per test case, calls the model, then judges.
Runs async; poll status via GET.

### GET /v1/eval-runs/{id}
Status, aggregate scores per rubric, cost, per-case results (paginated).

### GET /v1/eval-runs/diff?base={id}&candidate={id}
The regression report:
```json
{
  "base": {"name": "prompt_v1_sonnet", "aggregate": {"dietary_compliance": 4.4}},
  "candidate": {"name": "prompt_v2_haiku", "aggregate": {"dietary_compliance": 4.1}},
  "deltas": {
    "quality": {"dietary_compliance": -0.3},
    "cost_per_case_usd": {"base": 0.0041, "candidate": 0.0009, "delta_pct": -78.0},
    "avg_latency_ms": {"base": 1620, "candidate": 640, "delta_pct": -60.5}
  },
  "regressions": [
    {"test_case_id": "...", "rubric": "dietary_compliance", "base_score": 5,
     "candidate_score": 2, "judge_reasoning": "..."}
  ]
}
```
`regressions[]` lists cases where a score dropped ≥2 points — the interview money-shot.

---

## 5. Prompt Versions

### POST /v1/prompts
`{"prompt_key": "recipe_generator", "template": "...", "default_params": {...}}`
→ auto-increments `version` per key.

### GET /v1/prompts/{key}  ·  GET /v1/prompts/{key}/versions

---

## 6. Replay

### POST /v1/replays
```json
{"source_run_id": "...", "mode": "mock"}
```
- **mock:** server (or SDK helper) re-executes with stored LLM responses injected — deterministic, free, offline.
- **live:** same inputs, real LLM calls — produces a new run linked via `result_run_id`.

### GET /v1/replays/{id}
Status + link to the resulting run for side-by-side comparison with the source.

---

## 7. Error Format (uniform)
```json
{"error": {"code": "not_found", "message": "Run abc123 does not exist"}}
```
Codes: `invalid_request`, `unauthorized`, `not_found`, `conflict`, `rate_limited`, `internal`.
