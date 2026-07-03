# AgentLens — Build Roadmap (July 7 – Sep 30, 2026)

Budget: ~10–12 hrs/week alongside full-time work. Every week ends with something runnable.
Rule: if a week slips, cut scope from the SAME milestone — never push the resume-ready date.

---

## Phase 0 — Today (July 7): Repo bootstrap  — do this in one sitting

- [ ] Create GitHub repo `agentlens` (public, MIT license)
- [ ] Monorepo skeleton per 02-ARCHITECTURE §7 (sdk/, server/, dashboard/, examples/)
- [ ] `docker-compose.yml`: postgres:16 + redis:7
- [ ] server: FastAPI hello-world + SQLModel + Alembic wired, first migration runs
- [ ] sdk: package skeleton, `init()` no-op, pytest configured
- [ ] GitHub Actions: lint (ruff) + tests on push
- [ ] Commit docs from this package into `docs/`

**Claude Code prompt to start with:** "Read docs/01-PRD.md, docs/02-ARCHITECTURE.md,
docs/03-API-SPEC.md, docs/04-SDK-DESIGN.md. Scaffold the monorepo exactly per
ARCHITECTURE §7 with docker-compose, Alembic initial migration implementing the
ERD, and CI. Do not implement features yet."

---

## MILESTONE 1 — Tracing MVP (July 7 – Aug 10)

### Week 1 (Jul 7–13): Data layer + ingestion
- SQLModel models for PROJECT, RUN, SPAN, LLM_CALL (mirror ERD exactly)
- Alembic migration + indexes from ARCHITECTURE §5
- `POST /v1/ingest`: validation (pydantic), idempotent upsert, cost computation via pricing.py
- Run rollup updates (totals) on span/llm events
- Tests: ingest a synthetic 3-agent run fixture, assert tree + rollups

### Week 2 (Jul 14–20): SDK core
- `init/flush/shutdown`, EventBuffer + background shipper + retries
- `@trace` (sync + async) with contextvars nesting; `span()`; `run()`
- Unit tests for nesting correctness and non-blocking guarantees
- examples/quickstart.py works end-to-end against local server

### Week 3 (Jul 21–27): Provider patchers + query API
- `patch_anthropic()`, `patch_groq()` capturing tokens/model/messages
- GET /v1/runs, /v1/runs/{id}, /v1/runs/{id}/tree, /v1/spans/{id}
- GET /v1/analytics/costs + /latency
- Redis pub/sub on ingest + SSE endpoint for live runs

### Week 4 (Jul 28–Aug 3): Minimal dashboard
- React (Vite): runs list → trace tree (indented waterfall) → span detail drawer
- Cost overview page (bar by model, line by day) — recharts
- Live-run indicator via SSE (nice-to-have; cut first if slipping)

### Week 5 (Aug 4–10): M1 hardening + buffer
- docker-compose one-command demo with seeded data
- README v1: what/why, quickstart, architecture diagram
- **Checkpoint: demo "instrument an app in 3 lines, see the trace tree + costs"**

---

## MILESTONE 2 — Evaluation Engine (Aug 11 – Sep 7)  — RESUME-READY

### Week 6 (Aug 11–17): Datasets + rubrics
- CRUD: datasets, bulk test cases, rubrics, prompt versions
- Judge executor: render judge prompt, call judge model, parse strict-JSON score
- Retry/parse-failure handling (re-ask once, then mark unscored)

### Week 7 (Aug 18–24): Eval runs
- Mode A (score provided outputs) + Mode B (server-executed single-prompt target)
- Async execution (FastAPI BackgroundTasks in V1 — Temporal is roadmap, not now)
- Aggregates per rubric; eval results in dashboard (table + score chips)

### Week 8 (Aug 25–31): Regression diff
- GET /v1/eval-runs/diff: quality/cost/latency deltas + regressions list (drop ≥2)
- Dashboard diff view: side-by-side with red/green deltas
- Build FitTrack eval dataset (50 cases) + 3 rubrics; run v1-vs-v2 prompt diff for real

### Week 9 (Sep 1–7): **Resume milestone**
- Polish + bugfix week; record first demo GIF
- ⭐️ Resume bullet goes live; LinkedIn Projects section updated; repo pinned on GitHub
- Start applying with it from here on

**Resume bullet (M2 version):**
> Built AgentLens, an open-source LLM observability & evaluation platform:
> distributed tracing for multi-agent pipelines with per-call token/cost/latency
> analytics, LLM-as-judge evaluation pipelines, and automated regression
> detection across prompt and model versions (FastAPI, PostgreSQL, Redis, React).

---

## MILESTONE 3 — Replay + Flagship Polish (Sep 8 – Sep 30)

### Week 10 (Sep 8–14): Deterministic replay
- POST /v1/replays (mock + live), replay client in SDK (ordered stored-response queue)
- Dashboard: replay button on failed runs; source-vs-result comparison view

### Week 11 (Sep 15–21): FitTrack flagship demo
- Fully instrument FitTrack recipe pipeline (Groq) in prod
- Capture a real failure → replay it → fix → live re-run → document the story in README
- Benchmark numbers for README (ingest throughput, SDK overhead per call)

### Week 12 (Sep 22–30): Ship it
- Publish SDK to PyPI (`pip install agentlens`)
- Deploy dashboard + server with demo data (Railway/Render)
- README v2: 2-min demo video/GIF, architecture diagram, benchmarks, design
  decisions, honest "vs Langfuse/LangSmith" table, roadmap (the Phase-2/3 vision lives HERE)
- Resume bullet upgraded with replay + PyPI + deployment

**Resume bullet (final version):**
> Built and open-sourced AgentLens (PyPI), an LLM observability & evaluation
> platform with distributed multi-agent tracing, cost analytics, LLM-as-judge
> eval pipelines, prompt/model regression diffing, and deterministic replay of
> failed agent runs; dogfooded in production on a live app.

---

## Interview Prep Artifacts (produce as you build — 30 min/week)
- `docs/DESIGN-DECISIONS.md`: log every non-obvious choice + why (contextvars vs
  explicit passing, JSONB vs columns, server-side cost, BackgroundTasks vs Temporal)
- "Why not just Langfuse?" answer: regression diffing as a first-class API,
  deterministic mock-mode replay, self-hosted judge rubrics — know Langfuse's
  actual feature set so the comparison is accurate
- One-hour deep-dive readiness per area: SDK internals, schema, eval engine, replay

## Scope-Cut Priority (if weeks slip, cut in this order)
1. Live SSE runs view → 2. Latency percentiles → 3. Mode B server-executed evals
(keep Mode A) → 4. Streaming LLM support → 5. Dashboard polish
**Never cut:** trace tree, cost tracking, LLM-as-judge, regression diff, replay.
