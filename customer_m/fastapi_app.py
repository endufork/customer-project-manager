"""FastAPI application entry point.

This module is the migration target for the current http.server based app.
The first step keeps existing business modules and frontend API paths intact.
"""

from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api.auth import router as auth_router
from .api.bootstrap import router as bootstrap_router
from .api.projects import router as projects_router
from .config import STATIC_DIR
from .database import init_db
from .api.schemas import HealthPayload


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


app = FastAPI(title="项目管理系统", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth_router)
app.include_router(bootstrap_router)
app.include_router(projects_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def no_cache_static_pages(request, call_next):
    response = await call_next(request)
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
