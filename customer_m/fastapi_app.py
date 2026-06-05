"""FastAPI application entry point.

This module is the FastAPI entry point for the project management system.
Business behavior stays in customer_m.modules; API files only adapt HTTP calls.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api.auth import router as auth_router
from .api.bootstrap import router as bootstrap_router
from .api.projects import router as projects_router
from .api.workbench import router as workbench_router
from .config import STATIC_DIR
from .database import init_db
from .api.schemas import HealthPayload


logger = logging.getLogger(__name__)

STATIC_SCRIPT_PATHS = (
    "/static/js/app-core.js",
    "/static/js/auth.js",
    "/static/js/ui-shell.js",
    "/static/js/form-utils.js",
    "/static/js/project-config.js",
    "/static/js/project-library.js",
    "/static/js/workbench-config.js",
    "/static/js/workbench-utils.js",
    "/static/js/workbench-deliverables.js",
    "/static/js/workbench-due-dates.js",
    "/static/js/workbench-tasks.js",
    "/static/js/workbench-risks.js",
    "/static/js/workbench-view.js",
    "/static/app.js",
)


def static_asset_version() -> int:
    paths = [
        STATIC_DIR / "index.html",
        STATIC_DIR / "styles.css",
        STATIC_DIR / "app.js",
        *(STATIC_DIR / script.removeprefix("/static/") for script in STATIC_SCRIPT_PATHS),
    ]
    return max(int(path.stat().st_mtime) for path in paths if path.exists())


def render_index_html() -> str:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    version = static_asset_version()
    html = html.replace('/static/styles.css"', f'/static/styles.css?v={version}"')
    for script_path in STATIC_SCRIPT_PATHS:
        html = html.replace(f'{script_path}"', f'{script_path}?v={version}"')
    return html


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="项目管理系统", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth_router)
app.include_router(bootstrap_router)
app.include_router(projects_router)
app.include_router(workbench_router)


@app.middleware("http")
async def request_logging_and_cache_headers(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "Request failed method=%s path=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    duration_ms = (time.perf_counter() - started) * 1000
    log_message = "Request handled method=%s path=%s status=%s duration_ms=%.1f"
    log_args = (request.method, request.url.path, response.status_code, duration_ms)
    if response.status_code >= 400:
        logger.warning(log_message, *log_args)
    elif request.url.path.startswith("/api/"):
        logger.info(log_message, *log_args)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/health", response_model=HealthPayload)
@app.get("/api/health", response_model=HealthPayload)
def health() -> HealthPayload:
    return HealthPayload()


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index() -> Response:
    return HTMLResponse(render_index_html())
