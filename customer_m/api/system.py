"""FastAPI system maintenance routes."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ..modules.system_maintenance import create_database_backup
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
