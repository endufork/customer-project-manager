"""FastAPI bootstrap and settings routes."""

from fastapi import APIRouter, Depends

from ..database import db_connect, set_setting
from ..modules.lookups import get_bootstrap_payload
from .deps import current_user, require_roles
from .schemas import SettingsUpdateRequest


router = APIRouter(prefix="/api", tags=["bootstrap"])


@router.get("/bootstrap")
def bootstrap(_: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return get_bootstrap_payload(conn)


def admin_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "admin")


@router.patch("/settings")
def update_settings(body: SettingsUpdateRequest, _: dict = Depends(admin_user)) -> dict:
    with db_connect() as conn:
        if body.project_root_path is not None:
            set_setting(conn, "project_root_path", body.project_root_path.strip())
        if body.backup_target_path is not None:
            set_setting(conn, "backup_target_path", body.backup_target_path.strip())
        conn.commit()
        return get_bootstrap_payload(conn)
