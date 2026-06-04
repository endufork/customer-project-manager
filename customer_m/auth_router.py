import sqlite3

from .database import db_connect
from .modules.auth import (
    authenticate_token,
    list_users,
    login_with_code,
    request_login_code,
    revoke_token,
    update_user,
)


class AuthRouterMixin:
    current_user: dict | None = None

    def bearer_token(self) -> str:
        header = self.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            return header[7:].strip()
        return ""

    def require_auth(self) -> dict:
        if self.current_user is not None:
            return self.current_user
        token = self.bearer_token()
        with db_connect() as conn:
            user = authenticate_token(conn, token)
            conn.commit()
        if user is None:
            raise PermissionError("请先登录")
        self.current_user = user
        return user

    def has_role(self, *roles: str) -> bool:
        user = self.require_auth()
        user_roles = set(user.get("roles", []))
        if "admin" in user_roles:
            return True
        return bool(user_roles.intersection(roles))

    def require_role(self, *roles: str) -> dict:
        user = self.require_auth()
        if not self.has_role(*roles):
            raise PermissionError("当前账号没有权限执行此操作")
        return user

    def handle_auth_get(self, path: str, query: dict[str, list[str]]) -> bool:
        if path == "/api/auth/me":
            return self.api_auth_me()
        if path == "/api/users":
            return self.api_users(query)
        return False

    def handle_auth_post(self, path: str) -> bool:
        if path == "/api/auth/request-code":
            return self.api_request_code()
        if path == "/api/auth/login":
            return self.api_login()
        if path == "/api/auth/logout":
            return self.api_logout()
        return False

    def handle_auth_patch(self, path: str) -> bool:
        if path.startswith("/api/users/"):
            user_id = path.rsplit("/", 1)[1]
            return self.api_update_user(user_id)
        return False

    def api_request_code(self) -> bool:
        data = self.read_json()
        with db_connect() as conn:
            payload = request_login_code(conn, data.get("email", ""))
            conn.commit()
        self.send_json(payload)
        return True

    def api_login(self) -> bool:
        data = self.read_json()
        with db_connect() as conn:
            payload = login_with_code(conn, data.get("email", ""), data.get("code", ""))
            conn.commit()
        self.send_json(payload)
        return True

    def api_logout(self) -> bool:
        with db_connect() as conn:
            revoke_token(conn, self.bearer_token())
            conn.commit()
        self.current_user = None
        self.send_json({"ok": True})
        return True

    def api_auth_me(self) -> bool:
        self.send_json({"user": self.require_auth()})
        return True

    def api_users(self, query: dict[str, list[str]]) -> bool:
        self.require_role("admin")
        with db_connect() as conn:
            payload = list_users(conn, query)
        self.send_json(payload)
        return True

    def api_update_user(self, user_id: str) -> bool:
        self.require_role("admin")
        data = self.read_json()
        with db_connect() as conn:
            payload = update_user(conn, user_id, data)
            conn.commit()
        self.send_json(payload)
        return True

    def auth_error(self, exc: Exception) -> None:
        status = 403 if self.current_user is not None else 401
        self.send_error_json(str(exc), status)

    def route_auth_get(self, path: str, query: dict[str, list[str]]) -> bool:
        try:
            return self.handle_auth_get(path, query)
        except PermissionError as exc:
            self.auth_error(exc)
            return True
        except Exception as exc:
            self.send_error_json(str(exc), 500)
            return True

    def route_auth_post(self, path: str) -> bool:
        try:
            return self.handle_auth_post(path)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
            return True
        except PermissionError as exc:
            self.auth_error(exc)
            return True
        except sqlite3.IntegrityError as exc:
            self.send_error_json(f"数据约束错误：{exc}", 400)
            return True
        except Exception as exc:
            self.send_error_json(str(exc), 500)
            return True

    def route_auth_patch(self, path: str) -> bool:
        try:
            return self.handle_auth_patch(path)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
            return True
        except PermissionError as exc:
            self.auth_error(exc)
            return True
        except sqlite3.IntegrityError as exc:
            self.send_error_json(f"数据约束错误：{exc}", 400)
            return True
        except Exception as exc:
            self.send_error_json(str(exc), 500)
            return True
