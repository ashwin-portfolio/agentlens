# AgentLens — Architecture & ERD (V1)

## 1. System Overview

```
┌───────────────────────────────────────────────────────────────┐
│                        USER'S APPLICATION                       │
│  (e.g., FitTrack recipe pipeline, any multi-agent workflow)     │
│                                                                 │
│   @trace decorators + patched Anthropic/Groq clients            │
│   └── agentlens SDK (buffers events, ships async in batches)    │
└─────────────────────────────┬───────────────────────────────────┘
                            │ HTTPS POST /v1/ingest (batched JSON)
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                    AGENTLENS SERVER (FastAPI)                   │
│                                                                 │
│  Ingestion API ──► validate ──► compute cost ──► write Postgres │
│       │                                                         │
│       └──► publish to Redis (live run updates)                  │
│                                                                 │
│  Query API      ──► runs, traces, spans, analytics aggregations │
│  Eval Engine    ──► datasets, rubrics, LLM-as-judge, diffs      │
│  Replay Engine  ──► mock-mode & re-run-mode execution           │
└───────────┬───────────────────────────────┬─────────────────────┘
            │                             │
            ▼                             ▼
      ┌───────────┐                 ┌───────────┐
      │ PostgreSQL │                 │   Redis   │
      │ (SQLModel  │                 │ (pub/sub, │
      │ + Alembic) │                 │  buffers) │
      └───────────┘                 └───────────┘
            ▲
            │ REST/JSON (+ SSE from Redis for live runs)
            ▼
┌───────────────────────────────────────────────────────────────┐
│                    DASHBOARD (React, minimal)                   │
│   Runs list · Trace tree/waterfall · Span detail ·              │
│   Eval results · Regression diff · Cost charts                  │
└───────────────────────────────────────────────────────────────┘
```

## 2. Core Concepts (vocabulary — use consistently everywhere)

| Term | Meaning | Analogy (OpenTelemetry) |
|---|---|---|
| **Project** | A user application being observed (e.g., "fittrack-recipes") | Service |
| **Run** | One end-to-end execution of a pipeline (root of a trace tree) | Trace |
| **Span** | One unit of work inside a run: an agent step, an LLM call, a tool call | Span |
| **LLM Call** | A span of type `llm` with prompt/response/tokens/cost payload | — |
| **Dataset** | A set of test cases for evaluation | — |
| **Rubric** | A named scoring criterion with a judge prompt (score 1–5) | — |
| **Eval Run** | One execution of a target over a dataset, scored against rubrics | — |
| **Replay** | Re-execution of a recorded run (mock or live mode) | — |

Spans form a tree inside a run via `parent_span_id`. The SDK propagates the
current span through `contextvars`, so nesting is automatic.

## 3. Entity Relationship Diagram

```mermaid
erDiagram
    PROJECT ||--o{ RUN : has
    PROJECT ||--o{ DATASET : has
    PROJECT ||--o{ RUBRIC : has
    PROJECT ||--o{ PROMPT_VERSION : has
    RUN ||--o{ SPAN : contains
    SPAN ||--o{ SPAN : "parent of"
    SPAN ||--o| LLM_CALL : "detail (type=llm)"
    DATASET ||--o{ TEST_CASE : contains
    EVAL_RUN }o--|| DATASET : "evaluates over"
    EVAL_RUN ||--o{ EVAL_RESULT : produces
    EVAL_RESULT }o--|| TEST_CASE : "for case"
    EVAL_RESULT ||--o{ EVAL_SCORE : "scored by"
    EVAL_SCORE }o--|| RUBRIC : "against"
    EVAL_RUN }o--o| PROMPT_VERSION : "tests version"
    REPLAY }o--|| RUN : "replays"

    PROJECT {
        uuid id PK
        string name
        string api_key_hash
        timestamptz created_at
    }
    RUN {
        uuid id PK
        uuid project_id FK
        string name
        string status "running|completed|failed"
        jsonb metadata
        jsonb tags
        timestamptz started_at
        timestamptz ended_at
        numeric total_cost_usd
        int total_input_tokens
        int total_output_tokens
        int total_llm_calls
    }
    SPAN {
        uuid id PK
        uuid run_id FK
        uuid parent_span_id FK "nullable"
        string name
        string span_type "agent|llm|tool|function"
        string status "running|completed|failed"
        jsonb input
        jsonb output
        text error
        jsonb metadata
        timestamptz started_at
        timestamptz ended_at
        int latency_ms
    }
    LLM_CALL {
        uuid span_id PK_FK
        string provider "anthropic|groq"
        string model
        jsonb request_messages
        jsonb request_params "temperature, max_tokens..."
        jsonb response_content
        string finish_reason
        int input_tokens
        int output_tokens
        numeric cost_usd
    }
    PROMPT_VERSION {
        uuid id PK
        uuid project_id FK
        string prompt_key "e.g. recipe_generator"
        int version
        text template
        jsonb default_params
        timestamptz created_at
    }
    DATASET {
        uuid id PK
        uuid project_id FK
        string name
        text description
    }
    TEST_CASE {
        uuid id PK
        uuid dataset_id FK
        jsonb input
        jsonb expected "nullable reference output"
        jsonb metadata
    }
    RUBRIC {
        uuid id PK
        uuid project_id FK
        string name "correctness, groundedness..."
        text judge_prompt_template
        string judge_model
        int min_score
        int max_score
    }
    EVAL_RUN {
        uuid id PK
        uuid dataset_id FK
        uuid prompt_version_id FK "nullable"
        string name
        string target_model
        string status
        timestamptz started_at
        timestamptz ended_at
        numeric total_cost_usd
        jsonb aggregate_scores "rubric -> mean"
    }
    EVAL_RESULT {
        uuid id PK
        uuid eval_run_id FK
        uuid test_case_id FK
        jsonb output
        int latency_ms
        numeric cost_usd
        text error
    }
    EVAL_SCORE {
        uuid id PK
        uuid eval_result_id FK
        uuid rubric_id FK
        int score
        text judge_reasoning
    }
    REPLAY {
        uuid id PK
        uuid source_run_id FK
        string mode "mock|live"
        uuid result_run_id FK "the new run produced"
        timestamptz created_at
    }
```

## 4. Key Design Decisions

### D1 — SDK ships events async, never blocks the host app
Events go into an in-memory queue; a background thread flushes batches every
2s or 50 events. On server unavailability: retry with backoff, then drop with
a warning. **An observability tool must never take down the observed app.**

### D2 — Trace tree via contextvars, not explicit parent passing
```python
_current_span: ContextVar[Optional[SpanContext]] = ContextVar("agentlens_span", default=None)
```
Each `@trace` entry reads the current span as parent, sets itself as current,
restores on exit. Works with asyncio out of the box.

### D3 — Cost computed server-side at ingestion
SDK sends raw token counts; the server owns the pricing table
(`pricing.py`, per-model input/output USD per 1M tokens). Prices change;
updating the server updates everything. Store computed `cost_usd` on the row
so historical costs don't shift when prices update.

### D4 — Replay = stored LLM responses injected as mocks
Because every LLM_CALL row stores full request + response, mock-mode replay
patches the LLM client to return stored responses keyed by call sequence.
This makes any failure reproducible offline and free.
**This is the headline differentiator vs Langfuse — protect its scope.**

### D5 — Regression diff joins two eval runs on test_case_id
Same dataset + two eval runs — per-case score/cost/latency deltas + aggregate
means. No special storage needed; it's a query + a report view.

### D6 — Postgres JSONB for payloads, columns for query dimensions
Prompts/responses/metadata are JSONB (flexible, schemaless). Anything
filtered/aggregated on (status, model, timestamps, tokens, cost) is a real
column with an index.

## 5. Indexing Plan (day one)

```sql
CREATE INDEX idx_run_project_started ON run (project_id, started_at DESC);
CREATE INDEX idx_span_run ON span (run_id, started_at);
CREATE INDEX idx_span_parent ON span (parent_span_id);
CREATE INDEX idx_llm_call_model ON llm_call (model);
CREATE INDEX idx_eval_result_run ON eval_result (eval_run_id);
CREATE INDEX idx_eval_score_result ON eval_score (eval_result_id);
```

## 6. Extensibility Hooks (design-for-later, build-never-in-V1)
- `span_type` is a string, not an enum in the DB — new types (retrieval, memory) need no migration.
- `provider` on LLM_CALL — OpenAI/Gemini adapters slot in later.
- PROMPT_VERSION table exists in V1 (light usage) — full prompt registry later.
- Ingestion is one endpoint — can later swap Redis buffer for Kafka without touching the SDK.

## 7. Repository Layout (monorepo)

```
agentlens/
├── README.md                  # product-grade: diagram, GIF, benchmarks, roadmap
├── docker-compose.yml         # postgres + redis + server + dashboard
├── sdk/                       # published to PyPI as `agentlens`
│   ├── pyproject.toml
│   └── agentlens/
│       ├── __init__.py        # trace, trace_llm, init()
│       ├── client.py          # buffering + async shipping
│       ├── context.py         # contextvars propagation
│       ├── patchers/
│       │   ├── anthropic_patch.py
│       │   └── groq_patch.py
│       └── replay.py          # mock-mode client for replays
├── server/
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── models.py          # SQLModel entities (mirror ERD)
│       ├── pricing.py
│       ├── api/
│       │   ├── ingest.py
│       │   ├── runs.py
│       │   ├── analytics.py
│       │   ├── evals.py
│       │   └── replay.py
│       ├── services/
│       │   ├── evaluation.py  # judge orchestration
│       │   ├── regression.py  # diff computation
│       │   └── replayer.py
│       └── live.py            # Redis pub/sub → SSE
├── dashboard/                 # minimal React (Vite), 2-week budget
└── examples/
    ├── quickstart.py
    └── fittrack_demo/         # flagship demo instrumentation
```
