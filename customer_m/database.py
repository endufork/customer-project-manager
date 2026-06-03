import sqlite3

from .config import CATEGORY_DEFAULT_FOLDERS, DATA_DIR, DB_PATH, SCHEMA_PATH
from .utils import now_iso

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db_connect() as conn:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
        migrate_db(conn)
        conn.execute(
            "UPDATE project_statuses SET name = ? WHERE code = ?",
            ("待补WO号", "no_equipment_no"),
        )
        conn.execute(
            "UPDATE todo_types SET name = ? WHERE code = ?",
            ("补充WO号", "equipment_no_assignment"),
        )
        sync_file_category_defaults(conn)
        conn.commit()


def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row["name"] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
    if not column_exists(conn, table_name, column_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def sync_file_category_defaults(conn: sqlite3.Connection) -> None:
    for code, folder in CATEGORY_DEFAULT_FOLDERS.items():
        conn.execute(
            "UPDATE file_categories SET default_folder = ? WHERE code = ?",
            (folder, code),
        )

def migrate_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_groups (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL COLLATE NOCASE UNIQUE,
          short_name TEXT,
          country_region TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_sites (
          id TEXT PRIMARY KEY,
          customer_id TEXT NOT NULL,
          name TEXT NOT NULL,
          site_type TEXT,
          country_region TEXT,
          city TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON UPDATE CASCADE ON DELETE RESTRICT,
          UNIQUE (customer_id, name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_groups (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          customer_group_id TEXT,
          customer_id TEXT NOT NULL,
          site_id TEXT,
          shared_folder_path TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (customer_group_id) REFERENCES customer_groups(id) ON UPDATE CASCADE ON DELETE SET NULL,
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON UPDATE CASCADE ON DELETE RESTRICT,
          FOREIGN KEY (site_id) REFERENCES customer_sites(id) ON UPDATE CASCADE ON DELETE SET NULL,
          UNIQUE (customer_id, site_id, name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_group_files (
          id TEXT PRIMARY KEY,
          project_group_id TEXT NOT NULL,
          original_name TEXT NOT NULL,
          current_name TEXT NOT NULL,
          extension TEXT,
          category_code TEXT NOT NULL,
          file_path TEXT NOT NULL,
          size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
          modified_at TEXT,
          is_3d_model INTEGER NOT NULL DEFAULT 0 CHECK (is_3d_model IN (0, 1)),
          text_extracted INTEGER NOT NULL DEFAULT 0 CHECK (text_extracted IN (0, 1)),
          extracted_text TEXT,
          content_hash TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (project_group_id) REFERENCES project_groups(id) ON UPDATE CASCADE ON DELETE CASCADE,
          FOREIGN KEY (category_code) REFERENCES file_categories(code) ON UPDATE CASCADE ON DELETE RESTRICT,
          UNIQUE (project_group_id, file_path)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_tasks (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          work_package TEXT,
          phase_code TEXT,
          title TEXT NOT NULL,
          description TEXT,
          owner_name TEXT,
          status TEXT NOT NULL DEFAULT 'not_started',
          due_date TEXT,
          started_at TEXT,
          submitted_at TEXT,
          confirmed_at TEXT,
          completed_at TEXT,
          is_required INTEGER NOT NULL DEFAULT 1 CHECK (is_required IN (0, 1)),
          requires_deliverable INTEGER NOT NULL DEFAULT 0 CHECK (requires_deliverable IN (0, 1)),
          blocked_reason TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_deliverables (
          id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          file_id TEXT,
          deliverable_type TEXT,
          version_note TEXT,
          status TEXT NOT NULL DEFAULT 'submitted',
          submitted_by TEXT,
          submitted_at TEXT NOT NULL,
          confirmed_by TEXT,
          confirmed_at TEXT,
          reject_reason TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (task_id) REFERENCES execution_tasks(id) ON UPDATE CASCADE ON DELETE CASCADE,
          FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
          FOREIGN KEY (file_id) REFERENCES project_files(id) ON UPDATE CASCADE ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_issues (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          task_id TEXT,
          scope TEXT NOT NULL DEFAULT 'equipment',
          title TEXT NOT NULL,
          issue_type TEXT,
          source TEXT,
          severity TEXT NOT NULL DEFAULT 'medium',
          owner_name TEXT,
          status TEXT NOT NULL DEFAULT 'open',
          due_date TEXT,
          resolution TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          closed_at TEXT,
          FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
          FOREIGN KEY (task_id) REFERENCES execution_tasks(id) ON UPDATE CASCADE ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_activity_logs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          task_id TEXT,
          issue_id TEXT,
          activity_type TEXT NOT NULL,
          title TEXT NOT NULL,
          detail TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
          FOREIGN KEY (task_id) REFERENCES execution_tasks(id) ON UPDATE CASCADE ON DELETE SET NULL,
          FOREIGN KEY (issue_id) REFERENCES execution_issues(id) ON UPDATE CASCADE ON DELETE SET NULL
        )
        """
    )
    ensure_column(conn, "customers", "group_id", "group_id TEXT")
    ensure_column(conn, "contacts", "site_id", "site_id TEXT")
    ensure_column(conn, "contacts", "department", "department TEXT")
    ensure_column(conn, "projects", "project_group_id", "project_group_id TEXT")
    ensure_column(conn, "projects", "customer_group_id", "customer_group_id TEXT")
    ensure_column(conn, "projects", "site_id", "site_id TEXT")
    ensure_column(conn, "projects", "department", "department TEXT")
    ensure_column(conn, "projects", "origin_role", "origin_role TEXT")
    ensure_column(conn, "projects", "po_customer_id", "po_customer_id TEXT")
    ensure_column(conn, "projects", "project_nature", "project_nature TEXT")
    ensure_column(conn, "projects", "related_legacy_no", "related_legacy_no TEXT")
    ensure_column(conn, "projects", "status_date", "status_date TEXT")
    ensure_column(conn, "execution_issues", "scope", "scope TEXT NOT NULL DEFAULT 'equipment'")
    conn.execute("UPDATE execution_issues SET scope = 'task' WHERE task_id IS NOT NULL AND (scope IS NULL OR scope = 'equipment')")
    conn.execute("UPDATE execution_issues SET scope = 'equipment' WHERE scope IS NULL OR trim(scope) = ''")
    conn.execute("UPDATE projects SET project_nature = ? WHERE project_nature IS NULL OR trim(project_nature) = ''", ("新设备",))
    conn.execute(
        """
        UPDATE projects
        SET status_date = COALESCE(
            CASE
                WHEN status_code IN ('quoted', 'waiting_feedback') THEN quote_date
                WHEN status_code = 'po_received' THEN po_date
                WHEN status_code IN ('shipped', 'completed') THEN actual_ship_date
                WHEN status_code IN ('inquiry', 'no_equipment_no', 'clarification') THEN inquiry_date
                ELSE NULL
            END,
            inquiry_date
        )
        WHERE status_date IS NULL OR trim(status_date) = ''
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_group_id ON customers(group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_sites_customer_id ON customer_sites(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_site_id ON contacts(site_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_customer_group_id ON projects(customer_group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_project_group_id ON projects(project_group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_site_id ON projects(site_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_po_customer_id ON projects(po_customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project_groups_customer_id ON project_groups(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project_groups_site_id ON project_groups(site_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project_group_files_group_id ON project_group_files(project_group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_status_date ON projects(status_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_tasks_project_id ON execution_tasks(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_tasks_owner_name ON execution_tasks(owner_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_tasks_status ON execution_tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_tasks_due_date ON execution_tasks(due_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_deliverables_task_id ON task_deliverables(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_deliverables_project_id ON task_deliverables(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_deliverables_status ON task_deliverables(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_issues_project_id ON execution_issues(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_issues_status ON execution_issues(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_issues_severity ON execution_issues(severity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_issues_scope ON execution_issues(scope)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_logs_project_id ON execution_activity_logs(project_id)")


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row is None or row["value"] is None:
        return default
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, now_iso()),
    )
