from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import devices, diff, schema


def create_app(frontend_dir: Path | None = None, dev: bool = False) -> FastAPI:
    app = FastAPI(title="QYConv", version="1.0.0")

    if dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(devices.router, prefix="/api")
    app.include_router(diff.router, prefix="/api")
    app.include_router(schema.router, prefix="/api")

    if frontend_dir is not None and frontend_dir.exists():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app
