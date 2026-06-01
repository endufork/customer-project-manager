"""Compatibility exports for business services.

New code should import from customer_m.modules.* directly. The Web API still
imports this module so the first modularization pass can stay behavior-neutral.
"""

from .modules.lifecycle import create_default_project_todos, create_event, create_todo, generate_intake_no
from .modules.customers import get_or_create_customer_group, get_or_create_customer, get_or_create_site, get_or_create_contact
from .modules.projects import (
    create_project_record,
    delete_project_record,
    get_project_detail_payload,
    get_project_folder_path,
    get_project_shared_folder_path,
    list_project_records,
    normalize_project_nature,
    scan_project_shared_folder,
    update_project_record,
    validate_equipment_no,
)
from .modules.file_types import classify_file
from .modules.parsers import extract_text, extract_pdf_text, extract_docx_text, extract_xlsx_text
from .modules.folders import (
    customer_context_folder_for,
    project_group_folder_for,
    project_parent_folder_for,
    get_or_create_project_group,
    project_folder_for,
    ensure_standard_dirs,
    default_folder_for,
    unique_destination,
    unique_directory_destination,
    move_project_folder_if_needed,
    delete_project_folder_if_requested,
)
from .modules.scanner import sha256_file, category_from_project_path, scan_project_folder, scan_project_group_shared_folder
from .modules.file_import import iter_source_files, import_source_path

__all__ = [
    "generate_intake_no",
    "create_event",
    "create_todo",
    "create_default_project_todos",
    "get_or_create_customer_group",
    "get_or_create_customer",
    "get_or_create_site",
    "get_or_create_contact",
    "validate_equipment_no",
    "normalize_project_nature",
    "list_project_records",
    "get_project_detail_payload",
    "create_project_record",
    "update_project_record",
    "delete_project_record",
    "get_project_folder_path",
    "get_project_shared_folder_path",
    "scan_project_shared_folder",
    "classify_file",
    "extract_text",
    "extract_pdf_text",
    "extract_docx_text",
    "extract_xlsx_text",
    "customer_context_folder_for",
    "project_group_folder_for",
    "project_parent_folder_for",
    "get_or_create_project_group",
    "project_folder_for",
    "ensure_standard_dirs",
    "default_folder_for",
    "unique_destination",
    "unique_directory_destination",
    "move_project_folder_if_needed",
    "delete_project_folder_if_requested",
    "sha256_file",
    "category_from_project_path",
    "scan_project_folder",
    "scan_project_group_shared_folder",
    "iter_source_files",
    "import_source_path",
]
