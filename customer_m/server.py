import json
import os
import re
import sqlite3
import cgi
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import DB_PATH, STATIC_DIR
from .database import db_connect, init_db, set_setting
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
from .modules.workbench import (
    apply_template,
    create_issue,
    create_task,
    delete_issue,
    delete_task,
    get_workbench_project,
    list_workbench_inbox,
    list_workbench_projects,
    list_workbench_tasks,
    review_deliverable,
    submit_task_file,
    update_issue,
    update_task,
)
from .utils import safe_print


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


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "CustomerProjectPrototype/0.1"

    def end_headers(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean_path = parsed.path
        if clean_path == "/":
            return str(STATIC_DIR / "index.html")
        if clean_path.startswith("/static/"):
            return str(STATIC_DIR / clean_path.removeprefix("/static/"))
        return str(STATIC_DIR / clean_path.lstrip("/"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        if parsed.path in ("", "/", "/index.html"):
            self.send_index()
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_patch(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_delete(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def read_multipart(self) -> tuple[dict, str, bytes]:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        fields: dict[str, str] = {}
        for key in form.keys():
            item = form[key]
            if key == "file":
                continue
            if isinstance(item, list):
                fields[key] = item[0].value if item else ""
            else:
                fields[key] = item.value
        file_item = form["file"] if "file" in form else None
        if isinstance(file_item, list):
            file_item = file_item[0] if file_item else None
        if file_item is None or not getattr(file_item, "filename", ""):
            raise ValueError("请选择要上传的文件")
        return fields, Path(file_item.filename).name, file_item.file.read()

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_index(self) -> None:
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text(encoding="utf-8")
        version = self.static_asset_version()
        html = html.replace('/static/styles.css"', f'/static/styles.css?v={version}"')
        html = html.replace('/static/app.js"', f'/static/app.js?v={version}"')
        encoded = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def static_asset_version(self) -> int:
        paths = [STATIC_DIR / "index.html", STATIC_DIR / "styles.css", STATIC_DIR / "app.js"]
        return max(int(path.stat().st_mtime) for path in paths if path.exists())

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)

    def handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if path == "/api/bootstrap":
                return self.api_bootstrap()
            if path == "/api/workbench/projects":
                return self.api_workbench_projects(query)
            if path == "/api/workbench/inbox":
                return self.api_workbench_inbox(query)
            if path == "/api/workbench/tasks":
                return self.api_workbench_tasks(query)
            if path.startswith("/api/workbench/projects/"):
                project_id = path.rsplit("/", 1)[1]
                return self.api_workbench_project(project_id)
            if path == "/api/projects":
                return self.api_projects(query)
            project_id = match_project_id(path)
            if project_id is not None:
                return self.api_project_detail(project_id)
            self.send_error_json("接口不存在", 404)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_post(self, path: str) -> None:
        try:
            if path.startswith("/api/workbench/"):
                return self.handle_workbench_post(path)
            if path == "/api/projects":
                return self.api_create_project()
            action_match = match_project_action(path)
            if action_match is None:
                return self.send_error_json("接口不存在", 404)
            project_id, action = action_match
            if action == "scan":
                return self.api_scan_project(project_id)
            if action == "rename-folder":
                return self.api_rename_project_folder(project_id)
            if action == "open-folder":
                return self.api_open_project_folder(project_id)
            if action == "open-shared-folder":
                return self.api_open_shared_folder(project_id)
            if action == "scan-shared":
                return self.api_scan_shared_folder(project_id)
            self.send_error_json("接口不存在", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except sqlite3.IntegrityError as exc:
            self.send_error_json(f"数据约束错误：{exc}", 400)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_patch(self, path: str) -> None:
        try:
            if path.startswith("/api/workbench/"):
                return self.handle_workbench_patch(path)
            if path == "/api/settings":
                return self.api_update_settings()
            project_id = match_project_id(path)
            if project_id is not None:
                return self.api_update_project(project_id)
            self.send_error_json("接口不存在", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except sqlite3.IntegrityError as exc:
            self.send_error_json(f"数据约束错误：{exc}", 400)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_delete(self, path: str) -> None:
        try:
            if path.startswith("/api/workbench/"):
                return self.handle_workbench_delete(path)
            project_id = match_project_id(path)
            if project_id is not None:
                return self.api_delete_project(project_id)
            self.send_error_json("接口不存在", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
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

    def api_workbench_projects(self, query: dict[str, list[str]]) -> None:
        with db_connect() as conn:
            payload = list_workbench_projects(conn, query)
        self.send_json(payload)

    def api_workbench_inbox(self, query: dict[str, list[str]]) -> None:
        with db_connect() as conn:
            payload = list_workbench_inbox(conn, query)
        self.send_json(payload)

    def api_workbench_tasks(self, query: dict[str, list[str]]) -> None:
        with db_connect() as conn:
            payload = list_workbench_tasks(conn, query)
        self.send_json(payload)

    def api_workbench_project(self, project_id: str) -> None:
        with db_connect() as conn:
            payload = get_workbench_project(conn, project_id)
        self.send_json(payload)

    def handle_workbench_post(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[2] == "projects" and parts[4] == "tasks":
            data = self.read_json()
            with db_connect() as conn:
                payload = create_task(conn, parts[3], data)
                conn.commit()
            return self.send_json(payload, 201)
        if len(parts) == 5 and parts[2] == "projects" and parts[4] == "issues":
            data = self.read_json()
            with db_connect() as conn:
                payload = create_issue(conn, parts[3], data)
                conn.commit()
            return self.send_json(payload, 201)
        if len(parts) == 5 and parts[2] == "projects" and parts[4] == "templates":
            data = self.read_json()
            with db_connect() as conn:
                payload = apply_template(conn, parts[3], data.get("template"))
                conn.commit()
            return self.send_json(payload)
        if len(parts) == 5 and parts[2] == "tasks" and parts[4] == "deliverables":
            fields, filename, content = self.read_multipart()
            with db_connect() as conn:
                payload = submit_task_file(conn, parts[3], filename, content, fields)
                conn.commit()
            return self.send_json(payload, 201)
        return self.send_error_json("接口不存在", 404)

    def handle_workbench_patch(self, path: str) -> None:
        parts = path.strip("/").split("/")
        data = self.read_json()
        if len(parts) == 4 and parts[2] == "tasks":
            with db_connect() as conn:
                payload = update_task(conn, parts[3], data)
                conn.commit()
            return self.send_json(payload)
        if len(parts) == 4 and parts[2] == "issues":
            with db_connect() as conn:
                payload = update_issue(conn, parts[3], data)
                conn.commit()
            return self.send_json(payload)
        if len(parts) == 4 and parts[2] == "deliverables":
            with db_connect() as conn:
                payload = review_deliverable(conn, parts[3], data)
                conn.commit()
            return self.send_json(payload)
        return self.send_error_json("接口不存在", 404)

    def handle_workbench_delete(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[2] == "tasks":
            with db_connect() as conn:
                payload = delete_task(conn, parts[3])
                conn.commit()
            return self.send_json(payload)
        if len(parts) == 4 and parts[2] == "issues":
            with db_connect() as conn:
                payload = delete_issue(conn, parts[3])
                conn.commit()
            return self.send_json(payload)
        return self.send_error_json("接口不存在", 404)

    def api_project_detail(self, project_id: str) -> None:
        with db_connect() as conn:
            payload = get_project_detail_payload(conn, project_id)
            if payload is None:
                return self.send_error_json("项目不存在", 404)
        self.send_json(payload)

    def api_create_project(self) -> None:
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
        data = self.read_json()
        with db_connect() as conn:
            if "project_root_path" in data:
                set_setting(conn, "project_root_path", str(data["project_root_path"]).strip())
            if "backup_target_path" in data:
                set_setting(conn, "backup_target_path", str(data["backup_target_path"]).strip())
            conn.commit()
        self.api_bootstrap()

    def log_message(self, format: str, *args) -> None:
        safe_print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")


def main() -> None:
    init_db()
    port = int(os.environ.get("CUSTOMER_PROJECT_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), AppHandler)
    safe_print(f"Customer project prototype running at http://127.0.0.1:{port}")
    safe_print(f"Database: {DB_PATH}")
    server.serve_forever()
