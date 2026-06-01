import json
import os
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import DB_PATH, PROJECT_NATURE_OPTIONS, STATIC_DIR
from .database import db_connect, init_db, row_to_dict, set_setting
from .modules.customers import (
    get_or_create_contact,
    get_or_create_customer,
    get_or_create_customer_group,
    get_or_create_site,
)
from .modules.file_import import import_source_path
from .modules.folders import (
    delete_project_folder_if_requested,
    ensure_standard_dirs,
    get_or_create_project_group,
    move_project_folder_if_needed,
    project_folder_for,
    project_group_folder_for,
)
from .modules.lifecycle import create_event, generate_intake_no
from .modules.projects import normalize_project_nature, validate_equipment_no
from .modules.scanner import scan_project_folder, scan_project_group_shared_folder
from .utils import make_id, now_iso, safe_print

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
            payload = {
                "settings": {
                    row["key"]: row["value"]
                    for row in conn.execute("SELECT key, value FROM app_settings ORDER BY key")
                },
                "statuses": [
                    row_to_dict(row)
                    for row in conn.execute(
                        "SELECT code, name, sort_order FROM project_statuses WHERE is_active = 1 ORDER BY sort_order"
                    )
                ],
                "currencies": [
                    row_to_dict(row)
                    for row in conn.execute(
                        "SELECT code, name, symbol FROM currencies WHERE is_active = 1 ORDER BY code"
                    )
                ],
                "project_natures": list(PROJECT_NATURE_OPTIONS),
                "customer_groups": [
                    row_to_dict(row)
                    for row in conn.execute("SELECT id, name FROM customer_groups ORDER BY name")
                ],
                "customers": [
                    row_to_dict(row)
                    for row in conn.execute("SELECT id, group_id, name FROM customers ORDER BY name")
                ],
                "sites": [
                    row_to_dict(row)
                    for row in conn.execute("SELECT id, customer_id, name, site_type FROM customer_sites ORDER BY name")
                ],
                "project_groups": [
                    row_to_dict(row)
                    for row in conn.execute(
                        "SELECT id, customer_id, site_id, name, shared_folder_path FROM project_groups ORDER BY name"
                    )
                ],
                "contacts": [
                    row_to_dict(row)
                    for row in conn.execute(
                        "SELECT id, customer_id, site_id, name, role, department FROM contacts ORDER BY name"
                    )
                ],
            }
        self.send_json(payload)

    def api_projects(self, query: dict[str, list[str]]) -> None:
        filters = []
        params: list[str] = []
        search = (query.get("search", [""])[0] or "").strip()
        status = (query.get("status", [""])[0] or "").strip()
        customer_id = (query.get("customer_id", [""])[0] or "").strip()
        group_id = (query.get("group_id", [""])[0] or "").strip()
        site_id = (query.get("site_id", [""])[0] or "").strip()
        needs_equipment = (query.get("needs_equipment", [""])[0] or "").strip()

        if search:
            like = f"%{search}%"
            filters.append(
                """
                (
                  p.intake_no LIKE ?
                  OR p.equipment_no LIKE ?
                  OR p.equipment_name LIKE ?
                  OR p.project_name LIKE ?
                  OR p.project_nature LIKE ?
                  OR p.related_legacy_no LIKE ?
                  OR c.name LIKE ?
                  OR cg.name LIKE ?
                  OR cs.name LIKE ?
                  OR pg.name LIKE ?
                  OR co.name LIKE ?
                )
                """
            )
            params.extend([like, like, like, like, like, like, like, like, like, like, like])
        if status:
            filters.append("p.status_code = ?")
            params.append(status)
        if customer_id:
            filters.append("p.customer_id = ?")
            params.append(customer_id)
        if group_id:
            filters.append("p.customer_group_id = ?")
            params.append(group_id)
        if site_id:
            filters.append("p.site_id = ?")
            params.append(site_id)
        if needs_equipment == "1":
            filters.append("p.equipment_no IS NULL")

        where = "WHERE " + " AND ".join(filters) if filters else ""
        sql = f"""
            SELECT
              p.id, p.intake_no, p.equipment_no, p.equipment_name, p.project_name,
              p.project_nature, p.related_legacy_no,
              p.status_code, s.name AS status_name, p.currency_code,
              p.inquiry_date, p.expected_delivery_date, p.has_quote, p.has_po,
              p.has_3d_model, p.project_folder_path, p.created_at,
              cg.name AS customer_group_name, cs.name AS site_name, pg.name AS project_group_name, p.department,
              c.name AS customer_name, co.name AS contact_name,
              COUNT(f.id) AS file_count
            FROM projects p
            JOIN customers c ON c.id = p.customer_id
            LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
            LEFT JOIN customer_sites cs ON cs.id = p.site_id
            LEFT JOIN project_groups pg ON pg.id = p.project_group_id
            LEFT JOIN contacts co ON co.id = p.contact_id
            JOIN project_statuses s ON s.code = p.status_code
            LEFT JOIN project_files f ON f.project_id = p.id
            {where}
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT 200
        """
        with db_connect() as conn:
            rows = [row_to_dict(row) for row in conn.execute(sql, params)]
            kpis = row_to_dict(
                conn.execute(
                    """
                    SELECT
                      COUNT(*) AS total_projects,
                      COALESCE(SUM(CASE WHEN equipment_no IS NULL THEN 1 ELSE 0 END), 0) AS no_equipment_no,
                      COALESCE(SUM(CASE WHEN has_po = 1 THEN 1 ELSE 0 END), 0) AS with_po,
                      COALESCE(SUM(CASE WHEN has_3d_model = 1 THEN 1 ELSE 0 END), 0) AS with_model
                    FROM projects
                    """
                ).fetchone()
            )
        self.send_json({"projects": rows, "kpis": kpis})

    def api_project_detail(self, project_id: str) -> None:
        with db_connect() as conn:
            project = row_to_dict(
                conn.execute(
                    """
                    SELECT p.*, c.name AS customer_name, co.name AS contact_name, s.name AS status_name
                    , cg.name AS customer_group_name, cs.name AS site_name,
                      pg.name AS project_group_name, pg.shared_folder_path AS shared_folder_path,
                      po.name AS po_customer_name
                    FROM projects p
                    JOIN customers c ON c.id = p.customer_id
                    LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
                    LEFT JOIN customer_sites cs ON cs.id = p.site_id
                    LEFT JOIN project_groups pg ON pg.id = p.project_group_id
                    LEFT JOIN customers po ON po.id = p.po_customer_id
                    LEFT JOIN contacts co ON co.id = p.contact_id
                    JOIN project_statuses s ON s.code = p.status_code
                    WHERE p.id = ?
                    """,
                    (project_id,),
                ).fetchone()
            )
            if project is None:
                return self.send_error_json("项目不存在", 404)
            files = [
                row_to_dict(row)
                for row in conn.execute(
                    """
                    SELECT f.*, fc.name AS category_name
                    FROM project_files f
                    JOIN file_categories fc ON fc.code = f.category_code
                    WHERE f.project_id = ?
                    ORDER BY fc.sort_order, f.original_name
                    """,
                    (project_id,),
                )
            ]
            shared_files = []
            if project.get("project_group_id"):
                shared_files = [
                    row_to_dict(row)
                    for row in conn.execute(
                        """
                        SELECT f.*, fc.name AS category_name
                        FROM project_group_files f
                        JOIN file_categories fc ON fc.code = f.category_code
                        WHERE f.project_group_id = ?
                        ORDER BY fc.sort_order, f.original_name
                        """,
                        (project["project_group_id"],),
                    )
                ]
            events = [
                row_to_dict(row)
                for row in conn.execute(
                    "SELECT * FROM project_events WHERE project_id = ? ORDER BY created_at DESC LIMIT 50",
                    (project_id,),
                )
            ]
        self.send_json({"project": project, "files": files, "shared_files": shared_files, "events": events})

    def api_create_project(self) -> None:
        data = self.read_json()
        customer_group_name = (data.get("customer_group_name") or "").strip()
        customer_name = (data.get("customer_name") or "").strip()
        customer_id = (data.get("customer_id") or "").strip()
        site_name = (data.get("site_name") or "").strip()
        site_id = (data.get("site_id") or "").strip()
        project_group_name = (data.get("project_group_name") or "").strip()
        department = (data.get("department") or "").strip()
        contact_name = (data.get("contact_name") or "").strip()
        contact_id = (data.get("contact_id") or "").strip()
        origin_role = (data.get("origin_role") or "").strip()
        po_customer_name = (data.get("po_customer_name") or "").strip()
        equipment_name = (data.get("equipment_name") or "").strip()
        project_name = (data.get("project_name") or "").strip()
        project_nature = normalize_project_nature(data.get("project_nature") or "")
        related_legacy_no = (data.get("related_legacy_no") or "").strip()
        status_code = (data.get("status_code") or "inquiry").strip()
        currency_code = (data.get("currency_code") or "CNY").strip().upper()
        equipment_no_raw = (data.get("equipment_no") or "").strip()
        source_path = (data.get("source_path") or "").strip()
        inquiry_date = (data.get("inquiry_date") or "").strip() or None
        expected_delivery_date = (data.get("expected_delivery_date") or "").strip() or None
        quote_due_date = (data.get("quote_due_date") or "").strip()
        notes = (data.get("notes") or "").strip() or None

        if not equipment_name:
            raise ValueError("项目/设备/夹具名称不能为空")

        with db_connect() as conn:
            if not conn.execute("SELECT code FROM project_statuses WHERE code = ?", (status_code,)).fetchone():
                raise ValueError("项目状态无效")
            if not conn.execute("SELECT code FROM currencies WHERE code = ?", (currency_code,)).fetchone():
                raise ValueError("币种无效")

            equipment_no = validate_equipment_no(conn, equipment_no_raw)
            group_id = get_or_create_customer_group(conn, customer_group_name)
            customer_id = get_or_create_customer(conn, customer_id, customer_name, group_id)
            customer = conn.execute("SELECT name, group_id FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if group_id is None:
                group_id = customer["group_id"]
            site_id = get_or_create_site(conn, customer_id, site_id, site_name)
            contact_id = get_or_create_contact(
                conn,
                customer_id,
                site_id,
                contact_id,
                contact_name,
                (data.get("contact_role") or "").strip(),
                department,
            )
            contact = (
                conn.execute("SELECT name FROM contacts WHERE id = ?", (contact_id,)).fetchone()
                if contact_id
                else None
            )
            group = (
                conn.execute("SELECT name FROM customer_groups WHERE id = ?", (group_id,)).fetchone()
                if group_id
                else None
            )
            site = (
                conn.execute("SELECT name FROM customer_sites WHERE id = ?", (site_id,)).fetchone()
                if site_id
                else None
            )
            po_customer_id = (
                get_or_create_customer(conn, "", po_customer_name, group_id)
                if po_customer_name
                else customer_id
            )
            project_group_folder = None
            shared_folder = None
            project_group_id = None
            if project_group_name:
                project_group_folder = project_group_folder_for(
                    conn,
                    group["name"] if group else "",
                    customer["name"],
                    site["name"] if site else "",
                    project_group_name,
                )
                shared_folder = project_group_folder / SHARED_FOLDER_NAME
                shared_folder.mkdir(parents=True, exist_ok=True)
                project_group_id = get_or_create_project_group(
                    conn,
                    project_group_name,
                    group_id,
                    customer_id,
                    site_id,
                    shared_folder,
                )

            intake_no = generate_intake_no(conn)
            project_id = make_id()
            project_folder = project_folder_for(
                conn,
                group["name"] if group else "",
                customer["name"],
                site["name"] if site else "",
                project_group_name,
                contact["name"] if contact else "",
                equipment_name,
                intake_no,
                equipment_no,
            )
            ensure_standard_dirs(project_folder, conn)
            conn.execute(
                """
                INSERT INTO projects (
                  id, intake_no, equipment_no, source_type, customer_id, contact_id,
                  project_group_id, customer_group_id, site_id, department, origin_role, po_customer_id,
                  project_name, equipment_name, project_nature, related_legacy_no, status_code, currency_code,
                  inquiry_date, expected_delivery_date, project_folder_path,
                  original_source_path, has_quote, has_po, has_3d_model,
                  is_historical, is_data_complete, is_archived, notes, created_at, updated_at
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    project_id,
                    intake_no,
                    equipment_no,
                    "new",
                    customer_id,
                    contact_id,
                    project_group_id,
                    group_id,
                    site_id,
                    department or None,
                    origin_role or None,
                    po_customer_id,
                    project_name or None,
                    equipment_name,
                    project_nature,
                    related_legacy_no or None,
                    status_code,
                    currency_code,
                    inquiry_date,
                    expected_delivery_date,
                    str(project_folder),
                    source_path or None,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    notes,
                    now_iso(),
                    now_iso(),
                ),
            )
            create_event(conn, project_id, "project_created", "创建新项目", intake_no)
            imported_count, has_model = import_source_path(conn, project_id, project_folder, source_path)
            has_quote = 1 if conn.execute(
                "SELECT 1 FROM project_files WHERE project_id = ? AND category_code IN ('customer_quote', 'internal_quote') LIMIT 1",
                (project_id,),
            ).fetchone() else 0
            has_po = 1 if conn.execute(
                "SELECT 1 FROM project_files WHERE project_id = ? AND category_code = 'po' LIMIT 1",
                (project_id,),
            ).fetchone() else 0
            conn.execute(
                """
                UPDATE projects
                SET has_quote = ?, has_po = ?, has_3d_model = ?, updated_at = ?
                WHERE id = ?
                """,
                (has_quote, has_po, 1 if has_model else 0, now_iso(), project_id),
            )
            if imported_count:
                create_event(conn, project_id, "file_imported", f"导入 {imported_count} 个文件", source_path)
            if not equipment_no:
                conn.execute(
                    """
                    INSERT INTO todos (id, project_id, type_code, title, due_date, status, created_at, updated_at)
                    VALUES (?, ?, 'equipment_no_assignment', '补充内部设备号', ?, 'open', ?, ?)
                    """,
                    (make_id(), project_id, inquiry_date or datetime.now().date().isoformat(), now_iso(), now_iso()),
                )
            if quote_due_date:
                conn.execute(
                    """
                    INSERT INTO todos (id, project_id, type_code, title, due_date, status, created_at, updated_at)
                    VALUES (?, ?, 'quote_deadline', '完成并发送报价', ?, 'open', ?, ?)
                    """,
                    (make_id(), project_id, quote_due_date, now_iso(), now_iso()),
                )
            conn.commit()
        self.send_json({"id": project_id, "intake_no": intake_no, "project_folder_path": str(project_folder)}, 201)

    def api_scan_project(self, project_id: str) -> None:
        with db_connect() as conn:
            result = scan_project_folder(conn, project_id)
            conn.commit()
        self.send_json(result)

    def api_open_project_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            row = conn.execute(
                "SELECT project_folder_path FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise ValueError("项目不存在")
        folder = Path(row["project_folder_path"] or "")
        if not folder.exists():
            raise ValueError("项目文件夹不存在")
        os.startfile(str(folder))
        self.send_json({"opened": True, "path": str(folder)})

    def project_group_for_project(self, conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT pg.id, pg.shared_folder_path
            FROM projects p
            JOIN project_groups pg ON pg.id = p.project_group_id
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            raise ValueError("该项目未关联客户产品/生产线")
        return row

    def api_open_shared_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            group = self.project_group_for_project(conn, project_id)
        folder = Path(group["shared_folder_path"] or "")
        if not folder.exists():
            raise ValueError("共享资料文件夹不存在")
        os.startfile(str(folder))
        self.send_json({"opened": True, "path": str(folder)})

    def api_scan_shared_folder(self, project_id: str) -> None:
        with db_connect() as conn:
            group = self.project_group_for_project(conn, project_id)
            result = scan_project_group_shared_folder(conn, group["id"])
            if result["new_files"]:
                create_event(conn, project_id, "shared_folder_scanned", f"扫描共享资料，新增 {result['new_files']} 个文件")
            conn.commit()
        self.send_json(result)

    def api_update_project(self, project_id: str) -> None:
        data = self.read_json()
        customer_group_name = (data.get("customer_group_name") or "").strip()
        customer_name = (data.get("customer_name") or "").strip()
        customer_id = (data.get("customer_id") or "").strip()
        site_name = (data.get("site_name") or "").strip()
        site_id = (data.get("site_id") or "").strip()
        project_group_name = (data.get("project_group_name") or "").strip()
        department = (data.get("department") or "").strip()
        contact_name = (data.get("contact_name") or "").strip()
        contact_id = (data.get("contact_id") or "").strip()
        origin_role = (data.get("origin_role") or "").strip()
        po_customer_name = (data.get("po_customer_name") or "").strip()
        equipment_name = (data.get("equipment_name") or "").strip()
        project_name = (data.get("project_name") or "").strip()
        project_nature = normalize_project_nature(data.get("project_nature") or "")
        related_legacy_no = (data.get("related_legacy_no") or "").strip()
        status_code = (data.get("status_code") or "inquiry").strip()
        currency_code = (data.get("currency_code") or "CNY").strip().upper()
        equipment_no_raw = (data.get("equipment_no") or "").strip()
        inquiry_date = (data.get("inquiry_date") or "").strip() or None
        expected_delivery_date = (data.get("expected_delivery_date") or "").strip() or None
        notes = (data.get("notes") or "").strip() or None

        if not equipment_name:
            raise ValueError("项目/设备/夹具名称不能为空")

        with db_connect() as conn:
            existing = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if existing is None:
                raise ValueError("项目不存在")
            if not conn.execute("SELECT code FROM project_statuses WHERE code = ?", (status_code,)).fetchone():
                raise ValueError("项目状态无效")
            if not conn.execute("SELECT code FROM currencies WHERE code = ?", (currency_code,)).fetchone():
                raise ValueError("币种无效")

            equipment_no = validate_equipment_no(conn, equipment_no_raw, project_id)
            group_id = get_or_create_customer_group(conn, customer_group_name)
            customer_id = get_or_create_customer(conn, customer_id, customer_name, group_id)
            customer = conn.execute("SELECT group_id FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if group_id is None:
                group_id = customer["group_id"]
            site_id = get_or_create_site(conn, customer_id, site_id, site_name)
            contact_id = get_or_create_contact(
                conn,
                customer_id,
                site_id,
                contact_id,
                contact_name,
                (data.get("contact_role") or "").strip(),
                department,
            )
            po_customer_id = (
                get_or_create_customer(conn, "", po_customer_name, group_id)
                if po_customer_name
                else customer_id
            )
            group = (
                conn.execute("SELECT name FROM customer_groups WHERE id = ?", (group_id,)).fetchone()
                if group_id
                else None
            )
            customer_row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
            site = (
                conn.execute("SELECT name FROM customer_sites WHERE id = ?", (site_id,)).fetchone()
                if site_id
                else None
            )
            target_parent = project_parent_folder_for(
                conn,
                group["name"] if group else "",
                customer_row["name"],
                site["name"] if site else "",
                project_group_name,
            )
            current_project = conn.execute(
                "SELECT project_folder_path FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            current_leaf = (
                Path(current_project["project_folder_path"]).name
                if current_project and current_project["project_folder_path"]
                else ""
            )
            if current_leaf:
                target_project_folder = target_parent / current_leaf
            else:
                contact = (
                    conn.execute("SELECT name FROM contacts WHERE id = ?", (contact_id,)).fetchone()
                    if contact_id
                    else None
                )
                existing_project = conn.execute(
                    "SELECT intake_no FROM projects WHERE id = ?",
                    (project_id,),
                ).fetchone()
                target_project_folder = project_folder_for(
                    conn,
                    group["name"] if group else "",
                    customer_row["name"],
                    site["name"] if site else "",
                    project_group_name,
                    contact["name"] if contact else "",
                    equipment_name,
                    existing_project["intake_no"] if existing_project else "",
                    equipment_no,
                )
            project_group_id = None
            if project_group_name:
                shared_folder = target_parent / SHARED_FOLDER_NAME
                shared_folder.mkdir(parents=True, exist_ok=True)
                project_group_id = get_or_create_project_group(
                    conn,
                    project_group_name,
                    group_id,
                    customer_id,
                    site_id,
                    shared_folder,
                )
            move_project_folder_if_needed(conn, project_id, target_project_folder)

            conn.execute(
                """
                UPDATE projects
                SET equipment_no = ?,
                    project_group_id = ?,
                    customer_group_id = ?,
                    customer_id = ?,
                    site_id = ?,
                    department = ?,
                    origin_role = ?,
                    po_customer_id = ?,
                    contact_id = ?,
                    project_name = ?,
                    equipment_name = ?,
                    project_nature = ?,
                    related_legacy_no = ?,
                    status_code = ?,
                    currency_code = ?,
                    inquiry_date = ?,
                    expected_delivery_date = ?,
                    notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    equipment_no,
                    project_group_id,
                    group_id,
                    customer_id,
                    site_id,
                    department or None,
                    origin_role or None,
                    po_customer_id,
                    contact_id,
                    project_name or None,
                    equipment_name,
                    project_nature,
                    related_legacy_no or None,
                    status_code,
                    currency_code,
                    inquiry_date,
                    expected_delivery_date,
                    notes,
                    now_iso(),
                    project_id,
                ),
            )
            create_event(conn, project_id, "project_updated", "修改项目基础信息")
            conn.commit()
        self.send_json({"id": project_id, "updated": True})

    def api_delete_project(self, project_id: str) -> None:
        data = self.read_json()
        delete_files = bool(data.get("delete_files"))
        folder_deleted = False
        with db_connect() as conn:
            project = conn.execute(
                "SELECT project_folder_path FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ValueError("项目不存在")
            folder_path = project["project_folder_path"]
            if delete_files:
                folder_deleted = delete_project_folder_if_requested(conn, folder_path)
            conn.execute("DELETE FROM file_search WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
        self.send_json(
            {
                "deleted": True,
                "folder_deleted": folder_deleted,
                "project_folder_path": folder_path,
            }
        )

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
