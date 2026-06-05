"""Pydantic models for the FastAPI migration."""

from pydantic import BaseModel, Field


class HealthPayload(BaseModel):
    ok: bool = True
    app: str = "项目管理系统"


class ProjectListPayload(BaseModel):
    projects: list[dict] = Field(default_factory=list)
    kpis: dict = Field(default_factory=dict)


class ProjectDetailPayload(BaseModel):
    project: dict
    files: list[dict] = Field(default_factory=list)
    shared_files: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
