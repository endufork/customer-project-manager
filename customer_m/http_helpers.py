import cgi
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from .config import STATIC_DIR


class StaticAssetMixin:
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

    def send_index(self) -> None:
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text(encoding="utf-8")
        version = self.static_asset_version()
        html = html.replace('/static/styles.css"', f'/static/styles.css?v={version}"')
        for script_path in [
            "/static/js/app-core.js",
            "/static/js/auth.js",
            "/static/js/ui-shell.js",
            "/static/js/form-utils.js",
            "/static/js/project-config.js",
            "/static/js/project-library.js",
            "/static/js/workbench-config.js",
            "/static/js/workbench-utils.js",
            "/static/js/workbench-deliverables.js",
            "/static/js/workbench-due-dates.js",
            "/static/js/workbench-tasks.js",
            "/static/js/workbench-risks.js",
            "/static/js/workbench-view.js",
            "/static/app.js",
        ]:
            html = html.replace(f'{script_path}"', f'{script_path}?v={version}"')
        encoded = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def static_asset_version(self) -> int:
        paths = [
            STATIC_DIR / "index.html",
            STATIC_DIR / "styles.css",
            STATIC_DIR / "app.js",
            STATIC_DIR / "js" / "app-core.js",
            STATIC_DIR / "js" / "auth.js",
            STATIC_DIR / "js" / "ui-shell.js",
            STATIC_DIR / "js" / "form-utils.js",
            STATIC_DIR / "js" / "project-config.js",
            STATIC_DIR / "js" / "project-library.js",
            STATIC_DIR / "js" / "workbench-config.js",
            STATIC_DIR / "js" / "workbench-utils.js",
            STATIC_DIR / "js" / "workbench-deliverables.js",
            STATIC_DIR / "js" / "workbench-due-dates.js",
            STATIC_DIR / "js" / "workbench-tasks.js",
            STATIC_DIR / "js" / "workbench-risks.js",
            STATIC_DIR / "js" / "workbench-view.js",
        ]
        return max(int(path.stat().st_mtime) for path in paths if path.exists())


class JsonApiMixin:
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

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)
