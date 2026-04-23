from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer


def serve(
    host: str = typer.Option("127.0.0.1", help="Host interface"),
    port: int = typer.Option(8000, help="Port"),
    reload: bool = typer.Option(False, help="Enable auto-reload (dev)"),
    frontend_dir: Optional[Path] = typer.Option(
        None, help="Directory with built frontend (default: web/frontend/dist)"
    ),
) -> None:
    """Start the QYConv web GUI server (FastAPI + React build)."""
    import uvicorn

    default_dir = Path(__file__).resolve().parents[2] / "web" / "frontend" / "dist"
    effective_dir = frontend_dir if frontend_dir is not None else default_dir

    if not effective_dir.exists():
        typer.echo(
            f"Frontend build not found at {effective_dir}. "
            "Run 'cd web/frontend && npm run build' first.",
            err=True,
        )
        effective_dir = None  # type: ignore[assignment]

    if reload:
        import os

        os.environ["QYCONV_FRONTEND_DIR"] = str(effective_dir or "")
        os.environ["QYCONV_DEV"] = "1"
        uvicorn.run(
            "web.backend.app:create_app_lazy",
            host=host,
            port=port,
            reload=True,
            factory=True,
        )
    else:
        from web.backend.app import create_app

        app = create_app(frontend_dir=effective_dir, dev=reload)
        uvicorn.run(app, host=host, port=port)
