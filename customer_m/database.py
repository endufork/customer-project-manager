import sqlite3

from .config import CATEGORY_DEFAULT_FOLDERS, DATA_DIR, DB_PATH, SCHEMA_PATH
from .utils import now_iso

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
