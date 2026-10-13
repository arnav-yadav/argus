from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api import router
from app.config import settings
from app.db import SessionLocal
from app.metrics import register_slo_collector

app = FastAPI(
    title=f"{settings.app_name} API",
    description="SLO and uptime monitoring: heartbeats in, uptime and error budgets out.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator(excluded_handlers=["/health", "/ready", "/metrics"]).instrument(app).expose(
    app, include_in_schema=False
)
register_slo_collector(SessionLocal)

app.include_router(router)


@app.get("/")
def root():
    return {"name": f"{settings.app_name} API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    """Liveness: the process is up. Deliberately does not touch the database."""
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response):
    """Readiness: the database answers. Kubernetes stops routing traffic if it does not."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}
