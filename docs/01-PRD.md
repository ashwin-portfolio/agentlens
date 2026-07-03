# AgentLens — Product Requirements Document (V1)

> **Tagline:** Open-source observability and evaluation platform for multi-agent LLM systems — trace every step, score every output, replay every failure.

| Field | Value |
|---|---|
| Version | 1.0 (MVP) |
| Owner | Ashwin R |
| Status | In Development |
| Target completion | Mid-September 2026 (resume-ready milestone: mid-August 2026) |
| License | MIT (open source) |

---

## 1. Problem Statement

Teams deploying LLM agents in production cannot answer four basic questions:

1. **What did the agent actually do?** Multi-agent pipelines make nested LLM calls and tool calls that are invisible without instrumentation.
2. **What did it cost?** Token usage and spend per run, per agent, per model is untracked.
3. **Is quality getting better or worse?** Changing a prompt or swapping a model (e.g., Sonnet → Haiku) has unknown quality impact until users complain.
4. **Why did this run fail?** Failures cannot be reproduced because inputs, intermediate state, and model responses are not captured.

Existing tools (Langfuse, LangSmith) solve tracing well but are weak on **regression diffing across prompt versions** and **deterministic replay of failed multi-agent runs** — the two capabilities AgentLens makes first-class.

## 2. Goals (V1)

| # | Goal | Success metric |
|---|---|---|
| G1 | Trace any Python LLM workflow with ≤3 lines of integration code | SDK decorator works on a FastAPI app without code restructuring |
| G2 | Capture full multi-agent trace trees | Nested runs render as a tree: pipeline → agents → LLM/tool calls |
| G3 | Track cost, tokens, latency per call/agent/run/model | Dashboard totals match provider billing within ±2% |
| G4 | Score outputs automatically with LLM-as-judge | Configurable rubrics; batch eval over a dataset completes unattended |
| G5 | Detect regressions between prompt/model versions | Side-by-side diff report: quality delta, cost delta, latency delta |
| G6 | Deterministically replay any recorded run | Replayed run reproduces identical output from stored inputs |

## 3. Non-Goals (V1) — scope discipline

Explicitly **excluded** from V1. These go in the README roadmap, not the codebase:

- Authentication / multi-tenancy / RBAC
- Kubernetes deployment, Kafka, Ray
- Agent execution/orchestration (AgentLens observes agents; it does not run them)
- Memory systems, model routing, RL feedback loops
- Support for every LLM provider — V1 supports **Anthropic** and **Groq (OpenAI-compatible)** only
- JavaScript/TypeScript SDK
- Real-time alerting (email/Slack notifications)

## 4. Target Users

1. **Primary:** Backend/ML engineers running LLM pipelines in production (the interviewer persona).
2. **Secondary:** Solo developers with side-project LLM apps (the FitTrack dogfooding case).

## 5. Core Features

### F1 — Tracing SDK (`agentlens` on PyPI)
- `@trace` decorator for functions/agents; `@trace_llm` wrapper (or auto-patch) for Anthropic/Groq clients.
- Captures: prompts, responses, model, token counts (input/output), computed cost, latency, errors, custom metadata/tags.
- Nested calls form a parent-child **trace tree** via context propagation (contextvars).
- Non-blocking: events are buffered and shipped async in the background; SDK failure must never break the host app.

### F2 — Ingestion & Storage API (FastAPI service)
- REST endpoint receiving batched trace events from the SDK.
- Postgres for durable storage (SQLModel + Alembic migrations).
- Redis pub/sub for live "run in progress" streaming to the dashboard.

### F3 — Cost & Usage Analytics
- Per-model pricing table (configurable) — cost computed at ingestion.
- Aggregations: cost/tokens/latency by run, agent, model, day.

### F4 — Evaluation Engine
- **Rubrics:** named criteria (correctness, groundedness, tone…) each scored 1–5 by an LLM judge with a stored judging prompt.
- **Datasets:** collections of test cases (input + optional expected output/reference).
- **Eval runs:** execute a target function/prompt over a dataset, score all outputs, store scores.
- **Regression diff:** compare two eval runs (prompt v1 vs v2, or model A vs B) — per-case and aggregate deltas for quality, cost, latency.

### F5 — Deterministic Replay
- Every LLM call's inputs and outputs are stored.
- **Replay mode:** re-execute a recorded run where LLM calls return stored responses (mock mode) — reproduces the exact failure path for debugging.
- **Re-run mode:** execute same inputs with live LLM calls — tests whether a fix works.

### F6 — Dashboard (minimal, server-rendered or lightweight React)
- Runs list → trace tree view (waterfall) → span detail (prompt/response/tokens/cost).
- Eval results table + regression diff view.
- Cost overview charts.
- V1 rule: functional > beautiful. Two weeks max.

## 6. Flagship Demo (dogfooding)
Instrument **FitTrack's recipe recommendation pipeline** (Groq Llama 3.3 70B + Spoonacular) with AgentLens:
1. Trace every recipe generation end-to-end.
2. Build a 50-case eval dataset (user profiles → expected recipe properties).
3. Rubrics: nutritional accuracy, dietary-constraint compliance, response formatting.
4. Demo the regression diff: prompt v1 vs v2 quality/cost comparison.
5. Demo replay on a captured failure.

## 7. Milestones

| Milestone | Date | Contents |
|---|---|---|
| M1 — Tracing MVP | ~Aug 10, 2026 | F1 + F2 + F3, basic runs/trace view |
| M2 — Evaluation (**resume-ready**) | ~Sep 7, 2026 | F4 complete, regression diffs |
| M3 — Replay + polish | ~Sep 30, 2026 | F5, FitTrack demo, README, demo video, PyPI publish |

## 8. Success Criteria for the Job Search
- GitHub repo with architecture diagram, benchmark numbers, 2-min demo GIF/video.
- SDK installable via `pip install agentlens`.
- Live dashboard deployed (Railway/Render) with demo data.
- Resume bullet is 100% true: every claimed capability works and is demoable in an interview.
