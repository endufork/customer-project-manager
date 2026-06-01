from datetime import datetime
import re
import uuid

from .config import WINDOWS_RESERVED

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_print(message: str) -> None:
    try:
        if sys.stdout is not None:
            print(message, flush=True)
    except Exception:
        pass


def today_compact() -> str:
    return datetime.now().strftime("%Y%m%d")


def make_id() -> str:
    return str(uuid.uuid4())


def sanitize_path_part(value: str, fallback: str = "未命名") -> str:
    cleaned = WINDOWS_RESERVED.sub("_", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or fallback
