# FastAPI 重构计划 v0.1

## 目标

把当前基于 `http.server` 的本地服务重构为 FastAPI，以便后续团队试用、接口文档、权限中间件、文件上传、部署运维更清晰。

详细重构清单和代码审查红线见：

```text
fastapi-refactor-checklist-v0.1.md
```

## 为什么要重构

当前 HTTP 层的问题：

- 手写路由仍然偏脆弱。
- 请求解析、权限、异常处理散在多个 mixin 中。
- 没有自动 API 文档。
- 后续团队上线时，服务运行、日志、反向代理和健康检查不够标准。

FastAPI 可以带来：

- 清晰路由声明。
- Pydantic 请求/响应模型。
- 标准依赖注入权限校验。
- 自动 OpenAPI 文档。
- 更适合 Uvicorn/NAS/服务器部署。

## 迁移原则

- 不重写业务模块。
- 不改变前端 API 路径。
- 不改变数据库结构。
- 每次迁移一组路由，并保留可回退路径。

## 推荐阶段

### 阶段 1：基础应用骨架

- 新增 `customer_m/fastapi_app.py`。
- 新增 FastAPI 启动命令。
- 增加依赖：

```text
fastapi
uvicorn
python-multipart
```

- 保留旧 `run_server.cmd`，新增 FastAPI 启动脚本。
- 首批只迁移只读接口，不替换旧服务。

### 阶段 2：迁移基础接口

先迁移低风险接口：

```text
GET /api/bootstrap
GET /api/projects
GET /api/projects/{project_id}
```

### 阶段 3：迁移项目库写接口

```text
POST /api/projects
PATCH /api/projects/{project_id}
POST /api/projects/{project_id}/scan
POST /api/projects/{project_id}/rename-folder
DELETE /api/projects/{project_id}
```

### 阶段 4：迁移认证和用户管理

```text
POST /api/auth/request-code
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
GET /api/users
PATCH /api/users/{user_id}
```

### 阶段 5：迁移工作台

迁移任务、风险、交付物、Due Date 改期审批相关接口。

### 阶段 6：部署化

- 健康检查接口。
- 日志文件。
- Windows/NAS 启动方式。
- 环境变量配置说明。
- 局域网访问地址。

## 分支

FastAPI 重构从当前集成分支拉出：

```text
codex/team-trial-auth -> codex/fastapi-refactor
```

不要从旧 `main` 拉分支。
