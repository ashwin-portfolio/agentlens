# AgentLens

> Open-source observability and evaluation platform for multi-agent LLM systems — trace every step, score every output, replay every failure.

**Status:** early scaffolding — see [docs/05-ROADMAP.md](docs/05-ROADMAP.md). Full spec lives in [docs/](docs/).

## Development setup

```bash
# infrastructure (Postgres on localhost:5433, Redis on localhost:6379)
docker-compose up -d

# environment
cp .env.example .env   # fill in API keys

# install both packages (editable, with dev tools)
pip install -e "sdk/[dev]"
pip install -e "server/[dev]"

# run migrations, then start the server
(cd server && alembic upgrade head)
uvicorn app.main:app --app-dir server --reload   # GET /healthz → {"status": "ok"}

# lint & test
ruff check .
(cd sdk && pytest) && (cd server && pytest)
```
