"""FastAPI authentication and user management routes."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..modules.auth import AuthStateChangedError, list_users, login_with_code, request_login_code, revoke_token, update_user
from .deps import bearer_token, current_user, get_db, query_as_lists, require_roles
from .schemas import (
    CurrentUserPayload,
    LoginCodePayload,
    LoginCodeRequest,
    LoginPayload,
    LoginRequest,
    LogoutPayload,
    UpdateUserRequest,
    UserListPayload,
)


router = APIRouter(tags=["auth"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _integrity_error(exc: sqlite3.IntegrityError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据约束错误：{exc}")


def _model_data(body: UpdateUserRequest, *, exclude_unset: bool = False) -> dict:
    if callable(getattr(body, "model_dump", None)):
        return body.model_dump(exclude_unset=exclude_unset)
    return body.dict(exclude_unset=exclude_unset)


def admin_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "admin")


@router.post("/api/auth/request-code", response_model=LoginCodePayload)
def request_code(body: LoginCodeRequest, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    try:
        payload = request_login_code(conn, body.email)
        conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/api/auth/login", response_model=LoginPayload)
def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    try:
        payload = login_with_code(conn, body.email, body.code)
        conn.commit()
        return payload
    except AuthStateChangedError as exc:
        conn.commit()
        raise _bad_request(exc) from exc
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/api/auth/logout", response_model=LogoutPayload)
def logout(token: str = Depends(bearer_token), conn: sqlite3.Connection = Depends(get_db)) -> LogoutPayload:
    revoke_token(conn, token)
    conn.commit()
    return LogoutPayload()


@router.get("/api/auth/me", response_model=CurrentUserPayload)
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": user}


@router.get("/api/users", response_model=UserListPayload)
def users(request: Request, _: dict = Depends(admin_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return list_users(conn, query_as_lists(request))


@router.patch("/api/users/{user_id}")
def patch_user(
    user_id: str,
    body: UpdateUserRequest,
    _: dict = Depends(admin_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        payload = update_user(conn, user_id, _model_data(body, exclude_unset=True))
        conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc
