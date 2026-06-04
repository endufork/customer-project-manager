import os
import re
import sqlite3
from pathlib import Path

from .database import db_connect, set_setting
from .modules.lookups import get_bootstrap_payload
from .modules.projects import (
    create_project_record,
    delete_project_record,
    get_project_detail_payload,
    get_project_folder_path,
    get_project_shared_folder_path,
    list_project_records,
    rename_project_folder_to_wo,
    scan_project_shared_folder,
    update_project_record,
)
from .modules.scanner import scan_project_folder


PROJECT_ROUTE_RE = re.compile(r"^/api/projects/([^/]+)$")
PROJECT_ACTION_ROUTE_RE = re.compile(
    r"^/api/projects/([^/]+)/(scan|rename-folder|open-folder|open-shared-folder|scan-shared)$"
)


def match_project_id(path: str) -> str | None:
    match = PROJECT_ROUTE_RE.fullmatch(path)
    if match is None:
        return None
    return match.group(1)


def match_project_action(path: str) -> tuple[str, str] | None:
    match = PROJECT_ACTION_ROUTE_RE.fullmatch(path)
    if match is None:
        return None
    return match.group(1), match.group(2)


class ApiRouterMixin:
    def handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if path.startswith("/api/auth/") or path == "/api/users":
                if self.route_auth_get(path, query):
                    return
            self.require_auth()
            if path == "/api/bootstrap":
                return self.api_bootstrap()
            if path.startswith("/api/workbench/") and self.handle_workbench_get(path, query):
                return
            if path == "/api/projects":
                return self.api_projects(query)
            project_id = match_project_id(path)
            if project_id is not None:
                return self.api_project_detail(project_id)
            self.send_error_json("接口不存在", 404)
        except PermissionError as exc:
            self.auth_error(exc)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_post(self, path: str) -> None:
        try:
            if path.startswith("/api/auth/"):
                if self.route_auth_post(path):
                    return
            self.require_auth()
            if path.startswith("/api/workbench/"):
                if self.handle_workbench_post(path):
                    return
                return self.send_error_json("接口不存在", 404)
            if path == "/api/projects":
                return self.api_create_project()
            action_match = match_project_action(path)
            if action_match is None:
                return self.send_error_json("接口不存在", 404)
            project_id, action = action_match
            if action == "scan":
                self.require_role("pm")
                return self.api_scan_project(project_id)
            if action == "rename-folder":
                self.require_role("pm")
                return self.api_rename_project_folder(project_id)
            if action == "open-folder":
                return self.api_open_project_folder(project_id)
            if action == "open-shared-folder":
                return self.api_open_shared_folder(project_id)
            if action == "scan-shared":
                self.require_role("pm")
                return self.api_scan_shared_folder(project_id)
            self.send_error_json("接口不存在", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except sqlite3.IntegrityError as exc:
            self.send_error_json(f"数据约束错误：{exc}", 400)
        except PermissionError as exc:
            self.auth_error(exc)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_patch(self, path: str) -> None:
        try:
            if path.startswith("/api/auth/") or path.startswith("/api/users/"):
                if self.route_auth_patch(path):
                    return
            self.require_auth()
            if path.startswith("/api/workbench/"):
                if self.handle_workbench_patch(path):
                    return
                return self.send_error_json("接口不存在", 404)
            if path == "/api/settings":
                return self.api_update_settings()
            project_id = match_project_id(path)
            if project_id is not None:
                self.require_role("pm")
                return self.api_update_project(project_id)
            self.send_error_json("接口不存在", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except sqlite3.IntegrityError as exc:
            self.send_error_json(f"数据约束错误：{exc}", 400)
        except PermissionError as exc:
            self.auth_error(exc)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_delete(self, path: str) -> None:
        try:
            self.require_auth()
            if path.startswith("/api/workbench/"):
                if self.handle_workbench_delete(path):
                    return
                return self.send_error_json("接口不存在", 404)
            project_id = match_project_id(path)
            if project_id is not None:
                self.require_role("admin")
                return self.api_delete_project(project_id)
            self.send_error_json("接口不存在", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except PermissionError as exc:
            self.auth_error(exc)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def api_bootstrap(self) -> None:
        with db_connect() as conn:
            payload = get_bootstrap_payload(conn)
        self.send_json(payload)

    def api_projects(self, query: dict[str, list[str]]) -> None:
        with db_connect() as conn:
            payload = list_project_records(conn, query)
        self.send_json(payload)

    def api_project_detail(self, project_id: str) -> None:
        with db_connect() as conn:
            payload = get_project_detail_payload(conn, project_id)
            if payload is None:
                return self.send_error_json("项目不存在", 404)
        self.send_json(payload)

    def api_create_project(self) -> None:
        self.require_role("pm")
        data = self.read_json()
        with db_connect() as conn:
            payload = create_project_record(conn, data)
            conn.commit()
        self.send_json(payload, 201)

    def api_scan_project(self, project_id: str) -> None:
        with db_connect() as conn:
            result = scan_project_folder(conn, project_id)
            conn.commit()
        self.send_json(result)

    def api_rename_project_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            result = rename_project_folder_to_wo(conn, project_id)
            conn.commit()
        self.send_json(result)

    def api_open_project_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            folder_path = get_project_folder_path(conn, project_id)
        folder = Path(folder_path)
        if not folder.exists():
            raise ValueError("项目文件夹不存在")
        os.startfile(str(folder))
        self.send_json({"opened": True, "path": str(folder)})

    def api_open_shared_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            folder_path = get_project_shared_folder_path(conn, project_id)
        folder = Path(folder_path)
        if not folder.exists():
            raise ValueError("共享资料文件夹不存在")
        os.startfile(str(folder))
        self.send_json({"opened": True, "path": str(folder)})

    def api_scan_shared_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            result = scan_project_shared_folder(conn, project_id)
            conn.commit()
        self.send_json(result)

    def api_update_project(self, project_id: str) -> None:
        data = self.read_json()
        with db_connect() as conn:
            payload = update_project_record(conn, project_id, data)
            conn.commit()
        self.send_json(payload)

    def api_delete_project(self, project_id: str) -> None:
        data = self.read_json()
        delete_files = bool(data.get("delete_files"))
        with db_connect() as conn:
            payload = delete_project_record(conn, project_id, delete_files)
            conn.commit()
        self.send_json(payload)

    def api_update_settings(self) -> None:
        self.require_role("admin")
        data = self.read_json()
        with db_connect() as conn:
            if "project_root_path" in data:
                set_setting(conn, "project_root_path", str(data["project_root_path"]).strip())
            if "backup_target_path" in data:
                set_setting(conn, "backup_target_path", str(data["backup_target_path"]).strip())
            conn.commit()
        self.api_bootstrap()
