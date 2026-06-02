"""customers module."""

import sqlite3

from ..utils import make_id, now_iso

def get_or_create_customer_group(conn: sqlite3.Connection, group_name: str) -> str | None:
    group_name = group_name.strip()
    if not group_name:
        return None
    existing = conn.execute(
        "SELECT id FROM customer_groups WHERE name = ? COLLATE NOCASE",
        (group_name,),
    ).fetchone()
    if existing:
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO customer_groups (id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (new_id, group_name, now_iso(), now_iso()),
    )
    return new_id

def get_or_create_customer(
    conn: sqlite3.Connection,
    customer_id: str,
    name: str,
    group_id: str | None = None,
) -> str:
    if customer_id:
        row = conn.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if row:
            if group_id:
                conn.execute(
                    "UPDATE customers SET group_id = COALESCE(group_id, ?), updated_at = ? WHERE id = ?",
                    (group_id, now_iso(), customer_id),
                )
            return customer_id
    name = name.strip()
    if not name:
        raise ValueError("客户公司/法人主体不能为空")
    existing = conn.execute("SELECT id FROM customers WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if existing:
        if group_id:
            conn.execute(
                "UPDATE customers SET group_id = COALESCE(group_id, ?), updated_at = ? WHERE id = ?",
                (group_id, now_iso(), existing["id"]),
            )
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO customers (id, name, group_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (new_id, name, group_id, now_iso(), now_iso()),
    )
    return new_id

def get_or_create_site(
    conn: sqlite3.Connection,
    customer_id: str,
    site_id: str,
    name: str,
) -> str | None:
    if site_id:
        row = conn.execute("SELECT id FROM customer_sites WHERE id = ?", (site_id,)).fetchone()
        if row:
            return site_id
    name = name.strip()
    if not name:
        return None
    existing = conn.execute(
        "SELECT id FROM customer_sites WHERE customer_id = ? AND name = ? COLLATE NOCASE",
        (customer_id, name),
    ).fetchone()
    if existing:
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO customer_sites (id, customer_id, name, site_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (new_id, customer_id, name, "工厂/站点", now_iso(), now_iso()),
    )
    return new_id

def get_or_create_contact(
    conn: sqlite3.Connection,
    customer_id: str,
    site_id: str | None,
    contact_id: str,
    name: str,
    role: str = "",
    department: str = "",
) -> str | None:
    if contact_id:
        row = conn.execute("SELECT id FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE contacts
                SET site_id = COALESCE(?, site_id),
                    department = COALESCE(NULLIF(?, ''), department),
                    updated_at = ?
                WHERE id = ?
                """,
                (site_id, department.strip() or None, now_iso(), contact_id),
            )
            return contact_id
    name = name.strip()
    if not name:
        return None
    existing = conn.execute(
        "SELECT id FROM contacts WHERE customer_id = ? AND name = ? COLLATE NOCASE",
        (customer_id, name),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE contacts
            SET site_id = COALESCE(?, site_id),
                department = COALESCE(NULLIF(?, ''), department),
                updated_at = ?
            WHERE id = ?
            """,
            (site_id, department.strip() or None, now_iso(), existing["id"]),
        )
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO contacts (id, customer_id, site_id, name, role, department, is_primary, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            new_id,
            customer_id,
            site_id,
            name,
            role.strip() or None,
            department.strip() or None,
            now_iso(),
            now_iso(),
        ),
    )
    return new_id


def cleanup_orphan_site(conn: sqlite3.Connection, site_id: str | None) -> bool:
    if not site_id:
        return False
    referenced = conn.execute(
        """
        SELECT 1
        WHERE EXISTS (SELECT 1 FROM projects WHERE site_id = ?)
           OR EXISTS (SELECT 1 FROM contacts WHERE site_id = ?)
           OR EXISTS (SELECT 1 FROM project_groups WHERE site_id = ?)
        """,
        (site_id, site_id, site_id),
    ).fetchone()
    if referenced:
        return False
    conn.execute("DELETE FROM customer_sites WHERE id = ?", (site_id,))
    return True


def cleanup_orphan_customer(conn: sqlite3.Connection, customer_id: str | None) -> bool:
    if not customer_id:
        return False
    referenced = conn.execute(
        """
        SELECT 1
        WHERE EXISTS (SELECT 1 FROM projects WHERE customer_id = ? OR po_customer_id = ?)
           OR EXISTS (SELECT 1 FROM contacts WHERE customer_id = ?)
           OR EXISTS (SELECT 1 FROM customer_sites WHERE customer_id = ?)
           OR EXISTS (SELECT 1 FROM project_groups WHERE customer_id = ?)
        """,
        (customer_id, customer_id, customer_id, customer_id, customer_id),
    ).fetchone()
    if referenced:
        return False
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    return True


def cleanup_orphan_customer_context(
    conn: sqlite3.Connection,
    customer_id: str | None,
    site_id: str | None,
) -> None:
    cleanup_orphan_site(conn, site_id)
    cleanup_orphan_customer(conn, customer_id)
