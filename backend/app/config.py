"""
Central configuration for Metriva backend.

All environment-dependent values live here. Services and routes must import
from this module rather than reading environment variables directly, so that
configuration stays in one place as the project grows.
"""
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    # --- App metadata ---
    APP_NAME: str = "Metriva"
    APP_VERSION: str = "0.1.0"  # Phase 1: project scaffold
    API_PREFIX: str = "/api"

    # --- CORS ---
    # Vite's default dev server port. Extend this list (or set the env var)
    # when the frontend is deployed elsewhere.
    ALLOWED_ORIGINS: list[str] = os.environ.get(
        "METRIVA_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173"
    ).split(",")

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent  # backend/
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"

    # --- Database ---
    # SQLite for local dev per the architecture doc; switch by overriding
    # this env var once Postgres is available.
    DATABASE_URL: str = os.environ.get(
        "METRIVA_DATABASE_URL", f"sqlite:///{BASE_DIR / 'metriva.db'}"
    )


settings = Settings()
