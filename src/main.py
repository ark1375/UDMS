from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .settings import Settings
from .db import DuckDB
from .transactions import router as transactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load settings once
    settings = Settings()

    # Create DuckDB connection once
    db = DuckDB(settings.duckdb_path)
    db.connect()

    app.state.settings = settings
    app.state.db = db

    try:
        yield
    finally:
        db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Analytics CRUD API", version="1.0.0", lifespan=lifespan)

    api = FastAPI()
    api.include_router(transactions_router)

    # base_url/api/v1/*
    app.mount("/api/v1", api)
    return app


app = create_app()
