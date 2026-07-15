"""parsers module."""

import logging
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .. import config


logger = logging.getLogger(__name__)


def extract_text(path: Path) -> tuple[int, str]:
    ext = path.suffix.lower()
    try:
        if path.stat().st_size > config.PARSER_MAX_BYTES:
            logger.info(
                "Skipped text extraction above parser limit path=%s size_bytes=%s limit_bytes=%s",
                path,
                path.stat().st_size,
                config.PARSER_MAX_BYTES,
            )
            return 0, ""
    except OSError:
        logger.exception("Failed to inspect file before text extraction: %s", path)
        return 0, ""
    try:
        if ext in config.TEXT_EXTENSIONS:
            return 1, path.read_text(encoding="utf-8", errors="ignore")[:200_000]
        if ext == ".docx":
            return 1, extract_docx_text(path)[:200_000]
        if ext == ".xlsx":
            return 1, extract_xlsx_text(path)[:200_000]
        if ext == ".pdf":
            return 1, extract_pdf_text(path)[:200_000]
    except Exception:
        logger.exception("Failed to extract text from file: %s", path)
        return 0, ""
    return 0, ""

def extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)

def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    texts = [node.text or "" for node in root.findall(".//w:t", namespace)]
    return "\n".join(texts)

def extract_xlsx_text(path: Path) -> str:
    values: list[str] = []
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall(".//a:si", ns):
                parts = [node.text or "" for node in item.findall(".//a:t", ns)]
                shared_strings.append("".join(parts))
        for name in archive.namelist():
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for cell in root.findall(".//a:c", ns):
                value_node = cell.find("a:v", ns)
                if value_node is None or value_node.text is None:
                    continue
                if cell.attrib.get("t") == "s":
                    try:
                        values.append(shared_strings[int(value_node.text)])
                    except (ValueError, IndexError):
                        continue
                else:
                    values.append(value_node.text)
    return "\n".join(values)
