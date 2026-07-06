"""AgentLens server entrypoint.

Week 1: health check + ingestion. Query, analytics, eval, and replay routers
are added in roadmap Weeks 3-10 (docs/05-ROADMAP.md).
"""

from fastapi import FastAPI

from app.api.ingest import router as ingest_router

app = FastAPI(title="AgentLens", version="0.1.0")
app.include_router(ingest_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
