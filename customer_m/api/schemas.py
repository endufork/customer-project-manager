"""Pydantic models for the FastAPI migration."""

from pydantic import BaseModel, Field


class HealthPayload(BaseModel):
    ok: bool = True
    app: str = "项目管理系统"


class LoginCodeRequest(BaseModel):
    email: str = Field(default="", description="企业邮箱")


class LoginRequest(BaseModel):
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


class UpdateUserRequest(BaseModel):
    display_name: str = ""
    status: str = "enabled"
    roles: list[str] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    project_root_path: str | None = None
    backup_target_path: str | None = None


class ProjectMutationRequest(BaseModel):
    class Config:
        extra = "allow"


class DeleteProjectRequest(BaseModel):
    delete_files: bool = False


class WorkbenchMutationRequest(BaseModel):
    class Config:
        extra = "allow"


class WorkbenchTemplateRequest(BaseModel):
    template: str = ""


class ProjectListPayload(BaseModel):
    projects: list[dict] = Field(default_factory=list)
    kpis: dict = Field(default_factory=dict)


class ProjectDetailPayload(BaseModel):
    project: dict
    files: list[dict] = Field(default_factory=list)
    shared_files: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
