"""
Metriva backend entrypoint.

Phase 1 scope: application boots, exposes a health check, and is wired for
CORS so the frontend can reach it. Business routes (upload, merchants,
metrics, incidents, recovery, explanations) are added in later phases and
mounted here via app.include_router(...) — none exist yet by design.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import incidents, merchants
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Payment Intelligence & Revenue Recovery",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(merchants.router, prefix=settings.API_PREFIX)
app.include_router(incidents.router, prefix=settings.API_PREFIX)


@app.get(f"{settings.API_PREFIX}/health")
def health_check() -> dict:
    """Liveness/readiness probe used by the frontend and by ops tooling."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
def root() -> dict:
    return {
        "message": "Metriva API — see /docs for the OpenAPI schema.",
    }
