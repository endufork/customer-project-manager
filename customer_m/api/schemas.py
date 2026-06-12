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


class WorkbenchBoardProject(BaseModel):
    id: str
    current_number: str | None = None
    intake_no: str | None = None
    equipment_no: str | None = None
    customer_name: str | None = None
    customer_group_name: str | None = None
    site_name: str | None = None
    project_group_name: str | None = None
    equipment_name: str | None = None
    project_name: str | None = None
    project_nature: str | None = None
    status_code: str | None = None
    status_name: str | None = None
    workbench_area: str | None = None
    workbench_phase: str | None = None
    board_status: str
    board_status_label: str
    board_group: str
    board_group_label: str
    board_flags: list[str] = Field(default_factory=list)
    board_priority: int
    current_owner: str | None = None
    next_action: str | None = None
    next_task_id: str | None = None
    current_due_date: str | None = None
    expected_delivery_date: str | None = None
    task_total: int = 0
    task_done: int = 0
    overdue_tasks: int = 0
    blocked_tasks: int = 0
    waiting_info_tasks: int = 0
    rework_tasks: int = 0
    in_progress_tasks: int = 0
    due_soon_tasks: int = 0
    open_issues: int = 0
    high_issues: int = 0
    pending_deliverables: int = 0
    pending_completions: int = 0
    pending_due_date_requests: int = 0
    pending_risk_reviews: int = 0
    pending_total: int = 0


class WorkbenchBoardGroup(BaseModel):
    key: str
    label: str
    count: int


class WorkbenchBoardKpis(BaseModel):
    active_projects: int = 0
    due_soon_tasks: int = 0
    overdue_tasks: int = 0
    blocked_projects: int = 0
    pending_confirmations: int = 0
    high_risk_projects: int = 0


class WorkbenchBoardPayload(BaseModel):
    kpis: WorkbenchBoardKpis
    projects: list[WorkbenchBoardProject] = Field(default_factory=list)
    groups: list[WorkbenchBoardGroup] = Field(default_factory=list)
    current_user: dict = Field(default_factory=dict)


class WorkbenchRiskOverviewItem(BaseModel):
    id: str
    project_id: str
    task_id: str | None = None
    scope: str | None = None
    scope_label: str | None = None
    title: str
    issue_type: str | None = None
    source: str | None = None
    severity: str | None = None
    severity_label: str | None = None
    owner_name: str | None = None
    status: str
    status_label: str | None = None
    due_date: str | None = None
    resolution: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None
    task_title: str | None = None
    task_status: str | None = None
    current_number: str | None = None
    workbench_area: str | None = None
    intake_no: str | None = None
    equipment_no: str | None = None
    equipment_name: str | None = None
    project_name: str | None = None
    project_nature: str | None = None
    status_code: str | None = None
    expected_delivery_date: str | None = None
    customer_name: str | None = None
    customer_group_name: str | None = None
    site_name: str | None = None
    project_group_name: str | None = None
    contact_name: str | None = None
    is_overdue: bool = False
    is_due_soon: bool = False
    risk_priority: int = 0


class WorkbenchRiskOverviewKpis(BaseModel):
    active: int = 0
    high: int = 0
    overdue: int = 0
    due_soon: int = 0
    resolved: int = 0


class WorkbenchRiskOverviewPayload(BaseModel):
    risks: list[WorkbenchRiskOverviewItem] = Field(default_factory=list)
    kpis: WorkbenchRiskOverviewKpis
