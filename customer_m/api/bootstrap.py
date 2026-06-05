"""FastAPI bootstrap routes."""

from fastapi import APIRouter, Depends

from ..database import db_connect
from ..modules.lookups import get_bootstrap_payload
from .deps import current_user


router = APIRouter(prefix="/api", tags=["bootstrap"])


@router.get("/bootstrap")
def bootstrap(_: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return get_bootstrap_payload(conn)
