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

- `run_server.cmd` 改为 FastAPI 默认启动脚本，同时保留 `run_fastapi_server.cmd` 作为明确入口。
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

## 2026-06-05 阶段记录

### 已完成

- FastAPI 应用入口已成为当前后端主入口。
- 旧 `http.server` 入口已清理，不再维护双服务路径。
- 项目库、认证、用户管理、工作台核心接口已迁移为 FastAPI 路由。
- 请求体已从宽松模型收紧为明确 Pydantic Schema：
  - 项目创建/修改。
  - 登录验证码、登录、用户管理、系统设置。
  - 工作台任务、风险、Due Date 改期、交付物确认、任务模板。
- 所有请求模型默认禁止多余字段，避免前端误传字段被后端静默吞掉。
- 工作台 API 不再使用通用 `WorkbenchMutationRequest`，按业务动作拆分请求模型。
- 增加统一请求日志：
  - API 请求记录 method、path、status、duration。
  - 4xx/5xx 请求记录 warning。
  - 未捕获异常记录堆栈。
- 增强文件系统诊断日志：
  - 项目文件夹扫描。
  - 共享资料扫描。
  - 外部文件导入。
  - 项目目录迁移。
  - 项目目录回收站归档。
  - 工作台交付物写盘归档。
- 前端工作台表单采集已跳过 disabled 字段，避免 Schema 收紧后误触发 422。

### 最近提交

```text
8b14a22 refactor: tighten api schemas and diagnostics
```

### 验证结果

```text
.\tools\check.cmd
Python compile check: passed
pytest: 4 passed
JavaScript syntax check: passed
```

### 下一步

- 继续补充扫描流程的单文件失败记录，避免单个文件异常中断整个项目扫描。
- 优化文件扫描 N+1 查询，把现有文件记录预加载为字典。
- 增加针对 422 请求校验、文件系统失败、工作台关键写接口的测试。
- 规划日志落盘策略，区分开发控制台日志和团队试用运维日志。
