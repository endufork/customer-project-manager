"""FastAPI in-app notification routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import db_connect
from ..modules.notifications import list_notifications, mark_all_notifications_read, mark_notification_read
from .deps import current_user
from .schemas import NotificationReadRequest


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def notifications(limit: int = 30, user: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_notifications(conn, user["id"], limit)


@router.patch("/{notification_id}")
def read_notification(
    notification_id: str,
    body: NotificationReadRequest,
    user: dict = Depends(current_user),
) -> dict:
    if body.status != "read":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="通知状态只能更新为 read")
    try:
        with db_connect() as conn:
            payload = mark_notification_read(conn, notification_id, user["id"])
            conn.commit()
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/read-all")
def read_all_notifications(body: NotificationReadRequest, user: dict = Depends(current_user)) -> dict:
    if body.status != "read":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="通知状态只能更新为 read")
    with db_connect() as conn:
        payload = mark_all_notifications_read(conn, user["id"])
        conn.commit()
    return payload
