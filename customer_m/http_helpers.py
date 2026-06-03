import json
from http import HTTPStatus
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


class JsonApiMixin:
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
