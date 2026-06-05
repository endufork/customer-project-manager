"""FastAPI dependencies shared by API routers."""

from collections.abc import Iterator
import sqlite3

from fastapi import Header, HTTPException, Request, status

from ..database import db_connect
from ..modules.auth import authenticate_token


def get_db() -> Iterator[sqlite3.Connection]:
    conn = db_connect()
    try:
        yield conn
    finally:
        conn.close()


def bearer_token(authorization: str = Header(default="")) -> str:
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def current_user(token: str = Header(default="", alias="Authorization")) -> dict:
    clean_token = token[7:].strip() if token.lower().startswith("bearer ") else ""
    with db_connect() as conn:
        user = authenticate_token(conn, clean_token)
        conn.commit()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return user


def require_roles(user: dict, *roles: str) -> dict:
    user_roles = set(user.get("roles", []))
    if "admin" in user_roles or user_roles.intersection(roles):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有权限执行此操作")


def query_as_lists(request: Request) -> dict[str, list[str]]:
    query: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        query.setdefault(key, []).append(value)
    return query
