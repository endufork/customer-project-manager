"""Pydantic models for the FastAPI migration."""

from pydantic import BaseModel, ConfigDict, Field


class HealthPayload(BaseModel):
    ok: bool = True
    app: str = "项目管理系统"


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginCodeRequest(_StrictRequest):
    email: str = Field(default="", description="企业邮箱")


class LoginRequest(_StrictRequest):
    email: str = Field(default="", description="企业邮箱")
    code: str = Field(default="", description="6位验证码")


class LoginCodePayload(BaseModel):
    sent: bool
    message: str
    expires_in_seconds: int
    dev_code: str | None = None


class LoginPayload(BaseModel):
    token: str
    expires_at: str
    user: dict


class CurrentUserPayload(BaseModel):
    user: dict


class LogoutPayload(BaseModel):
    ok: bool = True


class UserListPayload(BaseModel):
    users: list[dict] = Field(default_factory=list)


class UpdateUserRequest(_StrictRequest):
    display_name: str = ""
    status: str = "enabled"
    roles: list[str] = Field(default_factory=list)


class SettingsUpdateRequest(_StrictRequest):
    project_root_path: str | None = None
    backup_target_path: str | None = None


class ProjectMutationRequest(_StrictRequest):
    customer_group_name: str | None = ""
    customer_name: str | None = ""
    customer_id: str | None = ""
    site_name: str | None = ""
    site_id: str | None = ""
    project_group_name: str | None = ""
    department: str | None = ""
    contact_name: str | None = ""
    contact_id: str | None = ""
    contact_role: str | None = ""
    origin_role: str | None = ""
    po_customer_name: str | None = ""
    equipment_name: str | None = ""
    project_name: str | None = ""
    project_nature: str | None = ""
    related_legacy_no: str | None = ""
    status_code: str | None = "inquiry"
    status_date: str | None = None
    currency_code: str | None = "CNY"
    equipment_no: str | None = ""
    source_path: str | None = ""
    inquiry_date: str | None = None
    quote_date: str | None = None
    po_date: str | None = None
    expected_delivery_date: str | None = None
    actual_ship_date: str | None = None
    quote_due_date: str | None = ""
    notes: str | None = None


class DeleteProjectRequest(_StrictRequest):
    delete_files: bool = False


class WorkbenchTaskRequest(_StrictRequest):
    title: str | None = ""
    work_package: str | None = None
    phase_code: str | None = None
    description: str | None = None
    owner_name: str | None = None
    status: str | None = None
    due_date: str | None = None
    is_required: str | int | bool | None = None
    requires_deliverable: str | int | bool | None = None
    blocked_reason: str | None = None
    linked_issue_id: str | None = None
    notes: str | None = None


class TaskCompletionRequest(_StrictRequest):
    completion_note: str | None = None
    submitted_by: str | None = None
    direct_confirm: bool | str | int | None = None


class TaskCompletionReviewRequest(_StrictRequest):
    status: str | None = None
    action: str | None = None
    confirmed_by: str | None = None
    reject_reason: str | None = None
    review_note: str | None = None


class WorkbenchIssueRequest(_StrictRequest):
    task_id: str | None = None
    scope: str | None = None
    title: str | None = ""
    issue_type: str | None = None
    source: str | None = None
    severity: str | None = None
    owner_name: str | None = None
    status: str | None = None
    due_date: str | None = None
    resolution: str | None = None
    review_note: str | None = None
    task_next_status: str | None = None


class DueDateChangeRequest(_StrictRequest):
    due_date: str | None = None
    proposed_due_date: str | None = None
    reason: str | None = None
    impact_note: str | None = None
    direct: bool | str | int | None = None


class DueDateReviewRequest(_StrictRequest):
    status: str | None = None
    action: str | None = None
    final_due_date: str | None = None
    review_note: str | None = None


class DeliverableReviewRequest(_StrictRequest):
    status: str | None = None
    action: str | None = None
    confirmed_by: str | None = None
    reject_reason: str | None = None


class WorkbenchTemplateRequest(_StrictRequest):
    template: str = ""


class ProjectListPayload(BaseModel):
    projects: list[dict] = Field(default_factory=list)
    kpis: dict = Field(default_factory=dict)


class ProjectDetailPayload(BaseModel):
    project: dict
    files: list[dict] = Field(default_factory=list)
    shared_files: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
