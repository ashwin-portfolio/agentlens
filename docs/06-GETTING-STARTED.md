# AgentLens — Getting Started Today (July 7)

How to go from zero to a working repo tonight, using Claude Code with these docs.

## Step 1 — Create the repo (5 min, do this manually)
```bash
# on GitHub: new public repo "agentlens", MIT license, Python .gitignore
git clone https://github.com/<you>/agentlens.git
cd agentlens
mkdir docs
# copy all 6 files from this documentation package into docs/
git add . && git commit -m "docs: add PRD, architecture, API spec, SDK design, roadmap"
```

## Step 2 — Feed Claude Code the context (the key habit)
Claude Code works dramatically better when it reads the docs first. Start every
session with:

> Read docs/01-PRD.md, docs/02-ARCHITECTURE.md, docs/03-API-SPEC.md,
> docs/04-SDK-DESIGN.md and docs/05-ROADMAP.md before doing anything.

Then give it ONE roadmap item at a time. Small tasks → review → commit. Never
"build the whole thing" — you must understand every file for interviews.

## Step 3 — Tonight's session prompts (in order)

**Prompt 1 — scaffold:**
> Read all files in docs/. Scaffold the monorepo exactly per ARCHITECTURE
> section 7: sdk/, server/, dashboard/ (empty for now), examples/. Set up
> docker-compose.yml with postgres:16 and redis:7, server FastAPI app with
> SQLModel + Alembic wired (empty initial migration), sdk package skeleton
> with pyproject.toml, pytest in both, ruff config, GitHub Actions CI running
> lint + tests. Don't implement any features yet.

**Prompt 2 — data layer:**
> Implement server/app/models.py with SQLModel entities exactly matching the
> ERD in docs/02-ARCHITECTURE.md section 3, generate the Alembic migration
> including the indexes from section 5, and add server/app/pricing.py with a
> pricing table for claude-sonnet-4-6, claude-haiku-4-5, and
> llama-3.3-70b-versatile (Groq). Write a test that creates a project, run,
> spans and an llm_call and asserts the tree relationships.

**Prompt 3 — ingestion:**
> Implement POST /v1/ingest per docs/03-API-SPEC.md section 1: pydantic
> validation of the event union, idempotent upserts on event id, server-side
> cost computation via pricing.py, run rollup updates, and Redis publish on
> run:{id}. Write tests using the API spec's example payload.

Stop there tonight. Review everything Claude Code wrote, make sure YOU can
explain each file, then commit.

## Step 4 — Session rhythm for the next 12 weeks
- Weeknights (2×1.5h): one roadmap sub-item per session
- Weekend (1×3–4h): the week's bigger item + tests + commit with clean messages
- Friday (15 min): update docs/DESIGN-DECISIONS.md with what you decided and why

## Rules that protect the interview value
1. **You review every line.** If you can't explain it, rewrite it or make
   Claude Code explain until you can. Interviewers WILL open your repo.
2. **Real commit history.** Steady commits over 12 weeks looks authentic;
   one 40,000-line initial commit screams "AI-generated in a weekend."
3. **Tests are not optional.** "How did you test this?" is a guaranteed question.
4. **Scope discipline.** Anything not in the PRD goes to README roadmap. Say no
   to yourself daily.

## Environment quick-reference
- Python 3.12, `uv` or pip — your call
- Postgres 16 via docker-compose (local port 5433 to avoid clashing with any
  existing local Postgres — matches your pgAdmin habits)
- Redis 7 via docker-compose
- Dashboard: Vite + React, added in Week 4 — ignore until then
- API keys needed: Anthropic (judge + demo agents), Groq (FitTrack demo) — put
  in .env, never commit
