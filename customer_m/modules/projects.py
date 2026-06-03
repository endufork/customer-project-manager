"""Project module facade.

Specific project behavior lives in project_rules, project_queries, and
project_commands. Importing from this module remains supported for API code and
legacy service callers.
"""

from .project_commands import (
    create_project_record,
    delete_project_record,
    rename_project_folder_to_wo,
    scan_project_shared_folder,
    update_project_record,
)
from .project_queries import (
    get_project_detail_payload,
    get_project_folder_path,
    get_project_shared_folder_path,
    list_project_records,
    project_group_for_project,
)
from .project_rules import normalize_project_nature, validate_equipment_no

__all__ = [
    "validate_equipment_no",
    "normalize_project_nature",
    "list_project_records",
    "get_project_detail_payload",
    "create_project_record",
    "update_project_record",
    "rename_project_folder_to_wo",
    "delete_project_record",
    "get_project_folder_path",
    "project_group_for_project",
    "get_project_shared_folder_path",
    "scan_project_shared_folder",
]
