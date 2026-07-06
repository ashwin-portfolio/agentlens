# AgentLens — Learning Log

This is a running reference of two things at once, updated with every PR:

1. **What we built** — a plain-English walkthrough of the code, so you can explain
   any file in this repo in an interview without re-reading it cold.
2. **The AI/ML and systems concepts behind it** — AgentLens is an LLM
   observability platform, which means building it touches token economics,
   LLM-as-judge evaluation, prompt versioning, and distributed tracing. You
   don't need prior ML background to follow this — concepts are introduced
   the first time the code needs them.

Each section maps to one roadmap item (docs/05-ROADMAP.md) and one PR. Read
the "Concepts" subsection *before* reviewing the PR diff — it'll make the code
click faster.

A running **Glossary** is at the bottom — new terms link back to where they
were introduced.

---

## Phase 0 — Repo bootstrap (`ad5a73d`)

### What we built
A monorepo skeleton: `sdk/` (the pip-installable `agentlens` package),
`server/` (the FastAPI backend), `dashboard/` (React, empty until Week 4),
`examples/`. Docker Compose runs local Postgres + Redis. Alembic (a
migration tool) is wired up with one empty migration so the "chain" of
schema changes exists from day one. CI runs lint + tests on every push.

### Why a monorepo?
SDK and server evolve together — a new event field means changing both. One
repo, one PR, one review, no version-mismatch bugs between "SDK v0.3 talking
to server v0.1". The tradeoff (documented in `02-ARCHITECTURE.md`) is that
SDK users only need `sdk/`, so it's still packaged as its own
`pyproject.toml` and published to PyPI separately in Week 12 — the monorepo
is an org choice, not a packaging choice.

### Why FastAPI + SQLModel + Alembic (concepts)
- **FastAPI**: a Python web framework built on type hints — you declare a
  Pydantic model for a request body and FastAPI validates it, documents it
  (auto-generated OpenAPI docs), and rejects bad input before your code runs.
- **SQLModel**: combines SQLAlchemy (the ORM — maps Python classes to SQL
  tables) with Pydantic (validation) into one model definition, so the same
  class is both your DB table *and* your API schema.
- **Alembic**: tracks schema changes as an ordered sequence of migration
  files (`0001_initial.py`, `0002_week1_tables.py`, …) so the schema's
  history is reproducible on any machine — `alembic upgrade head` always
  gets you to the current schema, and `alembic downgrade` can undo a step.
  This matters once real data exists — you can no longer just delete and
  recreate tables.

### Why Docker Compose for Postgres/Redis
Local Postgres and Redis, isolated per-project, torn down with one command
(`docker compose down`), no risk of colliding with any other Postgres you
have installed (hence the non-default port 5433 — see `.env.example`).

---

## Week 1 — Data layer + ingestion (`f1a527a`)

### What we built
Four database tables (`Project`, `Run`, `Span`, `LLMCall`) mirroring the ERD
in `02-ARCHITECTURE.md §3`, a pricing table for computing dollar cost from
token counts, and `POST /v1/ingest` — the one endpoint the SDK will call to
report what an LLM application did.

### Concept: what is "LLM observability"?
When a normal web app breaks, you have stack traces and logs. When an LLM
*agent* breaks, the failure is usually "the model produced a bad answer" —
there's no exception, no stack trace, just a wrong or low-quality output
three function calls deep in a pipeline you can't see into. LLM observability
means capturing enough data (what prompt went in, what came out, which model,
how many tokens, how long it took) that you can reconstruct *why* after the
fact, without re-running the whole system.

### Concept: Run / Span / Trace tree (borrowed from OpenTelemetry)
- A **Run** is one end-to-end execution — e.g. one user's "generate me a
  recipe" request.
- A **Span** is one unit of work inside that run — one agent's turn, one
  tool call, one LLM call. Spans nest: a `nutrition_agent` span might contain
  a `claude_call` LLM span inside it.
- This parent-child nesting forms a **tree**, reconstructed from each span's
  `parent_span_id`. This is the exact vocabulary used by
  [OpenTelemetry](https://opentelemetry.io/) (the industry-standard tracing
  spec for regular software) — AgentLens applies the same mental model to
  LLM pipelines specifically.
- Why it matters for ML engineering: multi-agent systems fail in ways that
  are only visible in the *shape* of the tree — e.g. an agent looping and
  calling itself 40 times, or a tool call's output silently not reaching the
  next agent. You can't see that in a flat log; you can see it instantly in
  a tree view.

### Concept: tokens and cost
LLM providers charge per **token** (roughly, a token ≈ ¾ of an English word),
separately for input tokens (what you send) and output tokens (what the
model generates) — output is usually priced several times higher than input,
because generating text is more compute-expensive than reading it. AgentLens
records `input_tokens`/`output_tokens` from the provider's response and
multiplies by a per-model price (`server/app/pricing.py`) to get `cost_usd`.
This is why the design deliberately computes cost **server-side**, never
trusting a client-sent value (see D3 in `02-ARCHITECTURE.md`) — prices change
over time, and centralizing the pricing table means one update fixes cost
calculations for every historical query, without ever rewriting stored rows
(the *computed* cost at ingestion time is stored permanently, so historical
totals don't shift retroactively when prices change later).

### Concept: idempotency (why `ON CONFLICT DO NOTHING`)
The SDK ships events over the network in the background (Week 2). Networks
fail; the SDK's retry logic might send the same event twice. If ingesting
twice created two database rows, your cost totals would silently double.
**Idempotency** means "doing the same operation twice has the same effect as
doing it once." We get this by keying every event on a client-generated UUID
and using Postgres's `INSERT ... ON CONFLICT (id) DO NOTHING` — a duplicate
insert is silently ignored rather than erroring or duplicating data. This is
a general distributed-systems pattern, not specific to AI — the same
technique shows up in payment processing, message queues, anywhere a
request might be retried.

### Concept: JSONB vs. real columns (D6)
Postgres's `JSONB` column type stores semi-structured data (like an LLM
prompt, which has no fixed shape) without needing a rigid schema. But you
can't efficiently filter or aggregate on JSONB at scale. The rule AgentLens
follows: **if you'll query/filter/sort by it, it's a real indexed column**
(`status`, `model`, `started_at`, `cost_usd`); **if it's just payload you'll
display but never filter by structure**, it's JSONB (`request_messages`,
`metadata`, `tags`). This is a common pattern in systems storing
heterogeneous LLM payloads next to relational data.

### Code concept: self-referential foreign keys (the span tree)
`Span.parent_span_id` is a foreign key pointing at `Span.id` — a table
referencing itself. This is the standard way to store a tree in a relational
database: each row knows only its immediate parent, and you reconstruct the
full tree by joining the table against itself (or, as the query API will do
in Week 3, walking it in application code).

### Code concept: Pydantic discriminated unions
The `/v1/ingest` endpoint accepts five different event shapes
(`run_start`, `span_start`, `span_end`, `llm_call`, `run_end`) in one list.
A **discriminated union** tells Pydantic "look at the `type` field first,
then validate against the matching model" — this is what lets one endpoint
safely parse a batch of mixed event types instead of five separate endpoints.

### Code concept: `contextvars` (previewed here, implemented Week 2)
Not used yet in Week 1, but worth knowing it's coming: Python's
`contextvars` module lets code know "what's the current span?" without
explicitly passing a `parent` argument through every function call. It's
what makes `@trace` "just work" when you nest decorated functions, including
across `async`/`await` boundaries. Covered in depth in the Week 2 entry.

---

## Glossary

| Term | Definition |
|---|---|
| Run | One end-to-end execution of a traced pipeline (the root of a trace tree) |
| Span | One unit of work inside a run (an agent step, tool call, or LLM call) |
| Trace tree | The parent-child nesting of spans inside a run, via `parent_span_id` |
| Token | The unit LLM providers bill by; roughly ¾ of an English word |
| Idempotent | An operation that has the same effect whether run once or many times |
| JSONB | Postgres's binary JSON column type — flexible schema, weaker query performance than real columns |
| Migration (Alembic) | A versioned, ordered file describing one schema change, so DB history is reproducible |
| Discriminated union | A Pydantic/type-system pattern: pick which shape to validate against based on one field's value |
| LLM-as-judge | *(Week 6 preview)* using an LLM to score another LLM's output against a rubric, instead of a human |
| Regression diff | *(Week 8 preview)* comparing two eval runs (e.g. prompt v1 vs v2) to see if quality/cost/latency got better or worse |
| Deterministic replay | *(Week 10 preview)* re-running a recorded failure with the exact same stored LLM responses, so the bug reproduces for free, offline |
