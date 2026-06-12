"""FastAPI engineering workbench routes."""

import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from ..database import db_connect
from ..modules.workbench import (
    apply_template,
    create_issue,
    create_task,
    delete_issue,
    delete_task,
    get_workbench_project,
    list_workbench_board,
    guard_regular_task_due_date_update,
    list_due_date_requests,
    list_workbench_inbox,
    list_workbench_pm_inbox,
    list_workbench_projects,
    list_workbench_risks,
    list_workbench_tasks,
    request_due_date_change,
    review_deliverable,
    review_due_date_change,
    review_task_completion,
    submit_task_file,
    submit_task_completion,
    update_issue,
    update_task,
)
from .deps import current_user, query_as_lists, require_roles
from .schemas import (
    DeliverableReviewRequest,
    DueDateChangeRequest,
    DueDateReviewRequest,
    TaskCompletionRequest,
    TaskCompletionReviewRequest,
    WorkbenchIssueRequest,
    WorkbenchBoardPayload,
    WorkbenchPmInboxPayload,
    WorkbenchRiskOverviewPayload,
    WorkbenchTaskRequest,
    WorkbenchTemplateRequest,
)


router = APIRouter(prefix="/api/workbench", tags=["workbench"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _integrity_error(exc: sqlite3.IntegrityError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据约束错误：{exc}")


def _model_data(body, *, exclude_unset: bool = False) -> dict:
    if callable(getattr(body, "model_dump", None)):
        return body.model_dump(exclude_unset=exclude_unset)
    return body.dict()


def pm_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "pm")


def engineer_or_pm_user(user: dict = Depends(current_user)) -> dict:
    return require_roles(user, "engineer", "pm")


@router.get("/projects")
def workbench_projects(request: Request, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_workbench_projects(conn, query_as_lists(request))


@router.get("/board", response_model=WorkbenchBoardPayload)
def workbench_board(request: Request, user: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_workbench_board(conn, query_as_lists(request), user)


@router.get("/risks", response_model=WorkbenchRiskOverviewPayload)
def workbench_risks(request: Request, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_workbench_risks(conn, query_as_lists(request))


@router.get("/inbox")
def workbench_inbox(request: Request, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_workbench_inbox(conn, query_as_lists(request))


@router.get("/pm-inbox", response_model=WorkbenchPmInboxPayload)
def workbench_pm_inbox(request: Request, _: dict = Depends(pm_user)) -> dict:
    with db_connect() as conn:
        return list_workbench_pm_inbox(conn, query_as_lists(request))


@router.get("/tasks")
def workbench_tasks(request: Request, _: dict = Depends(current_user)) -> dict:
    with db_connect() as conn:
        return list_workbench_tasks(conn, query_as_lists(request))


@router.get("/due-date-requests")
def due_date_requests(request: Request, _: dict = Depends(pm_user)) -> dict:
    with db_connect() as conn:
        return {"due_date_requests": list_due_date_requests(conn, query_as_lists(request))}


@router.get("/projects/{project_id}")
def workbench_project(project_id: str, _: dict = Depends(current_user)) -> dict:
    try:
        with db_connect() as conn:
            return get_workbench_project(conn, project_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
def add_task(project_id: str, body: WorkbenchTaskRequest, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = create_task(conn, project_id, _model_data(body))
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/projects/{project_id}/issues", status_code=status.HTTP_201_CREATED)
def add_issue(project_id: str, body: WorkbenchIssueRequest, _: dict = Depends(engineer_or_pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = create_issue(conn, project_id, _model_data(body))
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/projects/{project_id}/templates")
def add_template_tasks(project_id: str, body: WorkbenchTemplateRequest, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = apply_template(conn, project_id, body.template)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/tasks/{task_id}/deliverables", status_code=status.HTTP_201_CREATED)
async def submit_deliverable(
    task_id: str,
    category_code: str = Form(default="other"),
    deliverable_type: str = Form(default=""),
    version_note: str = Form(default=""),
    submitted_by: str = Form(default=""),
    file: UploadFile = File(...),
    _: dict = Depends(engineer_or_pm_user),
) -> dict:
    try:
        content = await file.read()
        fields = {
            "category_code": category_code,
            "deliverable_type": deliverable_type,
            "version_note": version_note,
            "submitted_by": submitted_by,
        }
        with db_connect() as conn:
            payload = submit_task_file(conn, task_id, file.filename or "upload", content, fields)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/tasks/{task_id}/due-date-requests", status_code=status.HTTP_201_CREATED)
def add_due_date_request(
    task_id: str,
    body: DueDateChangeRequest,
    user: dict = Depends(engineer_or_pm_user),
) -> dict:
    try:
        with db_connect() as conn:
            payload = request_due_date_change(conn, task_id, _model_data(body), user)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.post("/tasks/{task_id}/completion", status_code=status.HTTP_201_CREATED)
def submit_completion(
    task_id: str,
    body: TaskCompletionRequest,
    user: dict = Depends(engineer_or_pm_user),
) -> dict:
    try:
        with db_connect() as conn:
            payload = submit_task_completion(conn, task_id, _model_data(body), user)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.patch("/tasks/{task_id}/completion")
def patch_completion(
    task_id: str,
    body: TaskCompletionReviewRequest,
    user: dict = Depends(pm_user),
) -> dict:
    try:
        with db_connect() as conn:
            payload = review_task_completion(conn, task_id, _model_data(body), user)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, body: WorkbenchTaskRequest, _: dict = Depends(engineer_or_pm_user)) -> dict:
    try:
        with db_connect() as conn:
            data = guard_regular_task_due_date_update(conn, task_id, _model_data(body, exclude_unset=True))
            payload = update_task(conn, task_id, data)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.patch("/due-date-requests/{request_id}")
def patch_due_date_request(request_id: str, body: DueDateReviewRequest, user: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = review_due_date_change(conn, request_id, _model_data(body), user)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.patch("/issues/{issue_id}")
def patch_issue(issue_id: str, body: WorkbenchIssueRequest, user: dict = Depends(engineer_or_pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = update_issue(conn, issue_id, _model_data(body, exclude_unset=True), user)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.patch("/deliverables/{deliverable_id}")
def patch_deliverable(deliverable_id: str, body: DeliverableReviewRequest, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = review_deliverable(conn, deliverable_id, _model_data(body))
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.delete("/tasks/{task_id}")
def remove_task(task_id: str, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = delete_task(conn, task_id)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.delete("/issues/{issue_id}")
def remove_issue(issue_id: str, _: dict = Depends(pm_user)) -> dict:
    try:
        with db_connect() as conn:
            payload = delete_issue(conn, issue_id)
            conn.commit()
        return payload
    except ValueError as exc:
        raise _bad_request(exc) from exc
