"""FastAPI authentication and user management routes."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..database import db_connect
from ..modules.auth import list_users, login_with_code, request_login_code, revoke_token, update_user
from .deps import bearer_token, current_user, query_as_lists, require_roles
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


def _model_data(body: UpdateUserRequest) -> dict:
    if callable(getattr(body, "model_dump", None)):
        return body.model_dump()
    return body.dict()


def admin_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "admin")


@router.post("/api/auth/request-code", response_model=LoginCodePayload)
def request_code(body: LoginCodeRequest) -> dict:
    try:
        with db_connect() as conn:
            payload = request_login_code(conn, body.email)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/api/auth/login", response_model=LoginPayload)
def login(body: LoginRequest) -> dict:
    try:
        with db_connect() as conn:
            payload = login_with_code(conn, body.email, body.code)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/api/auth/logout", response_model=LogoutPayload)
def logout(token: str = Depends(bearer_token)) -> LogoutPayload:
    with db_connect() as conn:
        revoke_token(conn, token)
        conn.commit()
    return LogoutPayload()


@router.get("/api/auth/me", response_model=CurrentUserPayload)
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": user}


@router.get("/api/users", response_model=UserListPayload)
def users(request: Request, _: dict = Depends(admin_user)) -> dict:
    with db_connect() as conn:
        return list_users(conn, query_as_lists(request))


@router.patch("/api/users/{user_id}")
def patch_user(user_id: str, body: UpdateUserRequest, _: dict = Depends(admin_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = update_user(conn, user_id, _model_data(body))
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc
