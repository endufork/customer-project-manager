"""FastAPI project read routes for the first migration step."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..database import db_connect
from ..modules.projects import get_project_detail_payload, list_project_records
from .deps import current_user, query_as_lists
from .schemas import ProjectDetailPayload, ProjectListPayload


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListPayload)
def projects(request: Request, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_project_records(conn, query_as_lists(request))


@router.get("/{project_id}", response_model=ProjectDetailPayload)
def project_detail(project_id: str, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        payload = get_project_detail_payload(conn, project_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return payload
