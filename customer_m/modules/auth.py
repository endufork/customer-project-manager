from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import logging
import secrets
import smtplib
import sqlite3

from ..config import (
    AUTH_CODE_RESEND_SECONDS,
    AUTH_CODE_TTL_SECONDS,
    AUTH_EMAIL_DOMAIN,
    AUTH_SECRET,
    AUTH_SESSION_DAYS,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SECURITY,
    SMTP_USERNAME,
)
from ..database import row_to_dict
from ..utils import make_id, now_iso


VALID_ROLES = ("admin", "pm", "engineer", "readonly")
logger = logging.getLogger(__name__)


class AuthStateChangedError(ValueError):
    """Raised when an auth failure already changed persistent security state."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash_value(value: str) -> str:
    return hashlib.sha256(f"{AUTH_SECRET}:{value}".encode("utf-8")).hexdigest()


def _smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM_EMAIL and SMTP_USERNAME and SMTP_PASSWORD)


def normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("请输入有效的企业邮箱")
    domain = normalized.rsplit("@", 1)[1]
    if domain != AUTH_EMAIL_DOMAIN:
        raise ValueError(f"只允许 @{AUTH_EMAIL_DOMAIN} 企业邮箱登录")
    return normalized


def default_display_name(email: str) -> str:
    return email.split("@", 1)[0]


def user_payload(conn: sqlite3.Connection, user_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    roles = [
        item["role_code"]
        for item in conn.execute(
            "SELECT role_code FROM user_roles WHERE user_id = ? ORDER BY role_code",
            (user_id,),
        )
    ]
    payload = row_to_dict(row)
    payload["roles"] = roles
    payload["is_admin"] = "admin" in roles
    payload["is_pm"] = "pm" in roles
    payload["is_engineer"] = "engineer" in roles
    return payload


def ensure_user(conn: sqlite3.Connection, email: str) -> dict:
    from ..config import AUTH_INITIAL_ADMIN_EMAIL

    now = now_iso()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        user_id = make_id()
        conn.execute(
            """
            INSERT INTO users (id, email, display_name, status, created_at, updated_at)
            VALUES (?, ?, ?, 'enabled', ?, ?)
            """,
            (user_id, email, default_display_name(email), now, now),
        )
        conn.execute(
            "INSERT INTO user_roles (user_id, role_code, created_at) VALUES (?, 'readonly', ?)",
            (user_id, now),
        )
    else:
        user_id = row["id"]
    if email == AUTH_INITIAL_ADMIN_EMAIL:
        conn.execute("UPDATE users SET status = 'enabled', updated_at = ? WHERE id = ?", (now, user_id))
        for role in ("admin", "pm"):
            conn.execute(
                "INSERT OR IGNORE INTO user_roles (user_id, role_code, created_at) VALUES (?, ?, ?)",
                (user_id, role, now),
            )
    payload = user_payload(conn, user_id)
    if payload is None:
        raise ValueError("用户不存在")
    return payload


def request_login_code(conn: sqlite3.Connection, raw_email: str) -> dict:
    email = normalize_email(raw_email)
    ensure_user(conn, email)
    latest = conn.execute(
        """
        SELECT created_at FROM login_codes
        WHERE email = ? AND used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email,),
    ).fetchone()
    if latest:
        created_at = _parse_time(latest["created_at"])
        if created_at and (_now() - created_at).total_seconds() < AUTH_CODE_RESEND_SECONDS:
            raise ValueError("验证码发送太频繁，请稍后再试")

    code = f"{secrets.randbelow(1000000):06d}"
    created_at = _now()
    expires_at = created_at + timedelta(seconds=AUTH_CODE_TTL_SECONDS)
    conn.execute(
        """
        INSERT INTO login_codes (id, email, code_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (make_id(), email, _hash_value(f"{email}:{code}"), expires_at.isoformat(timespec="seconds"), created_at.isoformat(timespec="seconds")),
    )
    smtp_configured = _smtp_configured()
    sent = send_login_code_email(email, code)
    if smtp_configured and not sent:
        raise ValueError("验证码邮件发送失败，请稍后再试或联系管理员")
    payload = {
        "sent": sent,
        "message": "验证码已发送" if sent else "SMTP 未配置，已返回测试验证码",
        "expires_in_seconds": AUTH_CODE_TTL_SECONDS,
    }
    if not sent and not smtp_configured:
        payload["dev_code"] = code
    return payload


def send_login_code_email(email: str, code: str) -> bool:
    if not _smtp_configured():
        return False
    message = EmailMessage()
    message["Subject"] = "项目管理系统登录验证码"
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = email
    message.set_content(f"您的登录验证码是：{code}\n\n验证码 {AUTH_CODE_TTL_SECONDS // 60} 分钟内有效。")
    try:
        if SMTP_SECURITY == "starttls":
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
                smtp.send_message(message)
    except Exception:
        logger.exception("Failed to send login code email email=%s smtp_host=%s", email, SMTP_HOST)
        return False
    return True


def login_with_code(conn: sqlite3.Connection, raw_email: str, code: str) -> dict:
    email = normalize_email(raw_email)
    clean_code = (code or "").strip()
    if not clean_code:
        raise ValueError("请输入验证码")
    row = conn.execute(
        """
        SELECT * FROM login_codes
        WHERE email = ? AND used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email,),
    ).fetchone()
    if row is None:
        raise ValueError("请先获取验证码")
    if row["attempt_count"] >= 5:
        raise ValueError("验证码错误次数过多，请重新获取")
    expires_at = _parse_time(row["expires_at"])
    if expires_at is None or expires_at < _now():
        raise ValueError("验证码已过期，请重新获取")
    if row["code_hash"] != _hash_value(f"{email}:{clean_code}"):
        conn.execute(
            "UPDATE login_codes SET attempt_count = attempt_count + 1 WHERE id = ?",
            (row["id"],),
        )
        raise AuthStateChangedError("验证码不正确")

    user = ensure_user(conn, email)
    if user["status"] != "enabled":
        raise ValueError("该用户已停用，请联系管理员")
    token = secrets.token_urlsafe(32)
    now = _now()
    expires_at = now + timedelta(days=AUTH_SESSION_DAYS)
    conn.execute("UPDATE login_codes SET used_at = ? WHERE id = ?", (now.isoformat(timespec="seconds"), row["id"]))
    conn.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?", (now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"), user["id"]))
    conn.execute(
        """
        INSERT INTO auth_sessions (id, user_id, token_hash, expires_at, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (make_id(), user["id"], _hash_value(token), expires_at.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
    )
    return {"token": token, "expires_at": expires_at.isoformat(timespec="seconds"), "user": user_payload(conn, user["id"])}


def authenticate_token(conn: sqlite3.Connection, token: str | None) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        """
        SELECT * FROM auth_sessions
        WHERE token_hash = ? AND revoked_at IS NULL
        """,
        (_hash_value(token),),
    ).fetchone()
    if row is None:
        return None
    expires_at = _parse_time(row["expires_at"])
    if expires_at is None or expires_at < _now():
        return None
    conn.execute("UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?", (now_iso(), row["id"]))
    return user_payload(conn, row["user_id"])


def revoke_token(conn: sqlite3.Connection, token: str | None) -> None:
    if not token:
        return
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
        (now_iso(), _hash_value(token)),
    )


def list_users(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    search = (query.get("search") or [""])[0].strip().lower()
    rows = conn.execute(
        """
        SELECT users.* FROM users
        WHERE ? = ''
           OR lower(users.email) LIKE ?
           OR lower(COALESCE(users.display_name, '')) LIKE ?
        ORDER BY users.created_at DESC
        """,
        (search, f"%{search}%", f"%{search}%"),
    ).fetchall()
    if not rows:
        return {"users": []}

    user_ids = [row["id"] for row in rows]
    placeholders = ",".join("?" for _ in user_ids)
    role_rows = conn.execute(
        f"""
        SELECT user_id, role_code
        FROM user_roles
        WHERE user_id IN ({placeholders})
        ORDER BY role_code
        """,
        user_ids,
    ).fetchall()
    roles_by_user = {user_id: [] for user_id in user_ids}
    for role_row in role_rows:
        roles_by_user.setdefault(role_row["user_id"], []).append(role_row["role_code"])

    users = []
    for row in rows:
        payload = row_to_dict(row)
        roles = roles_by_user.get(row["id"], [])
        payload["roles"] = roles
        payload["is_admin"] = "admin" in roles
        payload["is_pm"] = "pm" in roles
        payload["is_engineer"] = "engineer" in roles
        users.append(payload)
    return {"users": users}


def update_user(conn: sqlite3.Connection, user_id: str, data: dict) -> dict:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("用户不存在")
    display_name = str(data.get("display_name", row["display_name"] or "")).strip()
    status = str(data.get("status", row["status"] or "enabled")).strip() or "enabled"
    if status not in ("enabled", "disabled"):
        raise ValueError("用户状态无效")
    now = now_iso()
    conn.execute(
        "UPDATE users SET display_name = ?, status = ?, updated_at = ? WHERE id = ?",
        (display_name, status, now, user_id),
    )
    if "roles" in data:
        roles = data.get("roles", [])
        if isinstance(roles, str):
            roles = [item.strip() for item in roles.split(",") if item.strip()]
        roles = [role for role in roles if role in VALID_ROLES]
        if not roles:
            roles = ["readonly"]
        conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        for role in sorted(set(roles)):
            conn.execute(
                "INSERT INTO user_roles (user_id, role_code, created_at) VALUES (?, ?, ?)",
                (user_id, role, now),
            )
    payload = user_payload(conn, user_id)
    if payload is None:
        raise ValueError("用户不存在")
    return payload
