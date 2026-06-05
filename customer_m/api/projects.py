"""FastAPI project routes."""

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..database import db_connect
from ..modules.projects import (
    create_project_record,
    delete_project_record,
    get_project_detail_payload,
    get_project_folder_path,
    get_project_shared_folder_path,
    list_project_records,
    rename_project_folder_to_wo,
    scan_project_shared_folder,
    update_project_record,
)
from ..modules.scanner import scan_project_folder
from .deps import current_user, query_as_lists, require_roles
from .schemas import DeleteProjectRequest, ProjectDetailPayload, ProjectListPayload, ProjectMutationRequest


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _integrity_error(exc: sqlite3.IntegrityError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据约束错误：{exc}")


def _model_data(body: ProjectMutationRequest) -> dict:
    if callable(getattr(body, "model_dump", None)):
        return body.model_dump()
    return body.dict()


def pm_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "pm")


def admin_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "admin")


@router.get("", response_model=ProjectListPayload)
def projects(request: Request, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_project_records(conn, query_as_lists(request))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectMutationRequest, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = create_project_record(conn, _model_data(body))
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.get("/{project_id}", response_model=ProjectDetailPayload)
def project_detail(project_id: str, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        payload = get_project_detail_payload(conn, project_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return payload


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectMutationRequest, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = update_project_record(conn, project_id, _model_data(body))
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.delete("/{project_id}")
def delete_project(project_id: str, body: DeleteProjectRequest | None = None, _: dict = Depends(admin_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = delete_project_record(conn, project_id, body.delete_files if body else False)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{project_id}/scan")
def scan_project(project_id: str, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = scan_project_folder(conn, project_id)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{project_id}/scan-shared")
def scan_shared_project_folder(project_id: str, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = scan_project_shared_folder(conn, project_id)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{project_id}/rename-folder")
def rename_project_folder(project_id: str, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = rename_project_folder_to_wo(conn, project_id)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{project_id}/open-folder")
def open_project_folder(project_id: str, _: dict = Depends(current_user)) -> dict:
    try:
        with db_connect() as conn:
            folder_path = get_project_folder_path(conn, project_id)
        folder = Path(folder_path)
        if not folder.exists():
            raise ValueError("项目文件夹不存在")
        os.startfile(str(folder))
        return {"opened": True, "path": str(folder)}
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except OSError as exc:
        raise _bad_request(f"打开项目文件夹失败，请检查网络路径或权限：{exc}") from exc


@router.post("/{project_id}/open-shared-folder")
def open_shared_project_folder(project_id: str, _: dict = Depends(current_user)) -> dict:
    try:
        with db_connect() as conn:
            folder_path = get_project_shared_folder_path(conn, project_id)
        folder = Path(folder_path)
        if not folder.exists():
            raise ValueError("共享资料文件夹不存在")
        os.startfile(str(folder))
        return {"opened": True, "path": str(folder)}
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except OSError as exc:
        raise _bad_request(f"打开共享资料文件夹失败，请检查网络路径或权限：{exc}") from exc
