import json
import os
import sqlite3
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
    scan_project_shared_folder,
    update_project_record,
)
from .modules.scanner import scan_project_folder
from .utils import safe_print

class AppHandler(SimpleHTTPRequestHandler):
    server_version = "CustomerProjectPrototype/0.1"

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

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)

    def handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if path == "/api/bootstrap":
                return self.api_bootstrap()
            if path == "/api/projects":
                return self.api_projects(query)
            if path.startswith("/api/projects/"):
                project_id = path.rsplit("/", 1)[1]
                return self.api_project_detail(project_id)
            self.send_error_json("接口不存在", 404)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_api_post(self, path: str) -> None:
        try:
            if path == "/api/projects":
                return self.api_create_project()
            if path.startswith("/api/projects/") and path.endswith("/scan"):
                project_id = path.split("/")[-2]
                return self.api_scan_project(project_id)
            if path.startswith("/api/projects/") and path.endswith("/open-folder"):
                project_id = path.split("/")[-2]
                return self.api_open_project_folder(project_id)
            if path.startswith("/api/projects/") and path.endswith("/open-shared-folder"):
                project_id = path.split("/")[-2]
                return self.api_open_shared_folder(project_id)
            if path.startswith("/api/projects/") and path.endswith("/scan-shared"):
                project_id = path.split("/")[-2]
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
            if path == "/api/settings":
                return self.api_update_settings()
            if path.startswith("/api/projects/"):
                project_id = path.rsplit("/", 1)[1]
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
            if path.startswith("/api/projects/"):
                project_id = path.rsplit("/", 1)[1]
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
