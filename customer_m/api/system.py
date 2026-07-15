"""FastAPI system maintenance routes."""

import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ..modules.system_maintenance import (
    create_database_backup,
    create_global_file_scan_job,
    get_global_file_scan_job,
    get_latest_global_file_scan_job,
    run_global_file_scan_job,
)
from .deps import current_user, require_roles


router = APIRouter(prefix="/api/system", tags=["system"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def admin_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "admin")


@router.post("/backup")
def backup_database(_: dict = Depends(admin_user)) -> dict:
    try:
        return create_database_backup()
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.Error as exc:
        raise _bad_request(exc) from exc


@router.get("/global-scan")
def latest_global_file_scan(_: dict = Depends(admin_user)) -> dict:
    try:
        return {"job": get_latest_global_file_scan_job()}
    except sqlite3.Error as exc:
        raise _bad_request(exc) from exc


@router.get("/global-scan/{job_id}")
def global_file_scan_status(job_id: str, _: dict = Depends(admin_user)) -> dict:
    try:
        return get_global_file_scan_job(job_id)
    except (ValueError, sqlite3.Error) as exc:
        raise _bad_request(exc) from exc


@router.post("/global-scan", status_code=status.HTTP_202_ACCEPTED)
def global_file_scan(
    background_tasks: BackgroundTasks,
    user: dict = Depends(admin_user),
) -> dict:
    try:
        job = create_global_file_scan_job(user)
        if job["created"]:
            background_tasks.add_task(run_global_file_scan_job, job["id"])
        return job
    except (ValueError, sqlite3.Error) as exc:
        raise _bad_request(exc) from exc
