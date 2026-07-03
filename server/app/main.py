"""AgentLens server entrypoint.

Phase 0: health check only. The ingestion, query, analytics, eval, and replay
routers are added in roadmap Weeks 1-10 (docs/05-ROADMAP.md).
"""

from fastapi import FastAPI

app = FastAPI(title="AgentLens", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
