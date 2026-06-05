# FastAPI 底层重构清单与代码审查标准 v0.1

## 适用背景

本系统用于非标设备制造团队的局域网项目管理。核心逻辑是监听并解析本地/共享盘物理文件夹结构，通过 INQ/WO 编号与数据库项目状态强绑定，实现自动归档、文件索引和状态流转。

当前 MVP 已跑通，但原有后端基于 Python `http.server` 和原生 `sqlite3`。为了支撑约 25 人团队高频并发使用，需要逐步升级底层架构。

当前重构分支：

```text
codex/fastapi-refactor
```

来源分支：

```text
codex/team-trial-auth
```

## 1. 框架升级

目标：把手写路由解析重构为 FastAPI 声明式路由。

执行要求：

- 使用 FastAPI `APIRouter` 拆分模块。
- 使用 Pydantic 进行请求体和响应体校验。
- 保持现有前端 API 路径不变。
- 不再新增手工字符串切片路由。
- 不再新增复杂正则路由解析。

首批迁移接口：

```text
GET /health
GET /api/bootstrap
GET /api/projects
GET /api/projects/{project_id}
```

验收标准：

- `/docs` 可打开。
- `/health` 可返回健康状态。
- `run_server.cmd` 和 `run_fastapi_server.cmd` 均启动 FastAPI 服务。
- 旧 `http.server` 入口已移除，不再维护双路由。

当前状态：

- 已完成 FastAPI 主入口、路由拆分、静态资源服务、健康检查和旧入口清理。
- 项目库、认证、用户管理、工作台核心接口已迁移。
- 请求体已使用 Pydantic 明确建模，并默认禁止多余字段。
- 后续新增 API 不允许回退到宽松字典请求体。

## 2. 性能优化：消除 N+1 查询

重点检查场景：

- 文件夹扫描。
- 项目列表。
- 项目详情。
- 工作台项目摘要。
- 任务、交付物、风险统计。

禁止模式：

```python
for file_path in files:
    conn.execute("SELECT ... WHERE file_path = ?", ...)
```

推荐模式：

```python
existing_files = {
    row["file_path"]: row
    for row in conn.execute(
        "SELECT id, file_path, size_bytes, modified_at, content_hash FROM project_files WHERE project_id = ?",
        (project_id,),
    )
}
```

验收标准：

- 扫描 1000 个文件时，不应出现 1000 次同类 SQL 查询。
- 列表页聚合数据尽量使用批量 SQL 或 `GROUP BY`。
- 扫描、列表、详情接口后续应补耗时日志。

当前状态：

- 工作台列表已做过 N+1 优化。
- 已增加 API 请求耗时日志。
- 文件夹扫描按当前业务频率保持轻量，不做实时监听。
- 文件夹扫描 N+1 优化降为中低优先级；如后续文件数量明显上升，再预加载 `project_files` / `project_group_files` 形成字典。

## 3. SQLite 高并发处理

当前要求：

```python
sqlite3.connect(DB_PATH, timeout=30)
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA busy_timeout = 30000
PRAGMA foreign_keys = ON
```

事务原则：

- 写事务要短。
- 不在持有数据库写锁时执行长时间网络盘 IO。
- 文件遍历、hash、文本解析尽量和批量写库分阶段处理。
- 后续如并发压力继续上升，再考虑单写队列或轻量连接池。

验收标准：

- 多用户读项目库不明显阻塞。
- PM 修改项目不频繁出现 `database is locked`。
- 文件扫描长耗时不长时间持有写锁。

## 4. 核心资产防灾机制

禁止直接永久删除客户资料。

禁止在生产业务逻辑中出现：

```python
shutil.rmtree(path)
Path.unlink()
os.remove(path)
```

目标策略：

1. 数据库软删除：

```text
is_deleted = 1
deleted_at
deleted_by
delete_reason
```

2. 物理文件移动到回收站：

```text
_RecycleBin_/
  2026-06-05/
    WO12345_项目名_deleted_20260605_153000/
```

3. 支持恢复：

- 恢复项目文件夹。
- 恢复单个文件。
- 恢复数据库记录。

验收标准：

- Admin 删除项目不会永久删除物理资料。
- 删除动作可追溯。
- 回收站路径和原路径都写入数据库。

## 5. 文件系统风险防护

风险来源：

- UNC/NAS 网络路径闪断。
- 权限不足。
- 文件被占用。
- 扫描过程中有人移动文件。
- 路径过长或文件名异常。

执行要求：

- 文件操作必须捕获：

```python
PermissionError
FileNotFoundError
OSError
```

- 单个文件失败不能中断整个项目扫描。
- 扫描结果应包含：

```json
{
  "new_files": 0,
  "updated_files": 0,
  "removed_files": 0,
  "failed_files": 0
}
```

- 后续新增 `file_scan_errors` 或同类审计表。

验收标准：

- 网络盘断开时返回明确错误。
- 无权限文件被记录，不导致整个扫描崩溃。
- 扫描失败可追踪。

当前状态：

- 已为目录迁移、回收站归档、外部导入、交付物归档、文件夹枚举增加异常日志。
- 当前扫描枚举失败可追踪并返回明确错误。
- 单个文件失败不会中断整个扫描。
- 扫描结果已包含 `failed_files` 和 `file_errors`。
- 暂不新增扫描错误数据库明细表；团队试用阶段先依赖返回结果和日志排错。

## 6. 分阶段执行

### 阶段 1：FastAPI 骨架

- 新增 FastAPI app。
- 新增独立启动脚本。
- 迁移只读接口。
- 保留旧服务入口。

### 阶段 2：数据库连接与扫描优化

- 统一连接 timeout/WAL。
- 消除扫描 N+1 查询。
- 降低数据库写锁持有时间。

### 阶段 3：删除防灾

- 增加软删除字段。
- 增加 `_RecycleBin_` 移动策略。
- 移除直接物理删除。

### 阶段 4：文件系统异常补偿

- 扫描错误记录。
- 网络盘异常处理。
- 权限失败提示。

### 阶段 5：迁移写接口和工作台

- 项目创建/修改/扫描。
- 登录权限。
- 任务、风险、交付物、Due Date。

### 阶段 6：部署化

- 健康检查。
- OpenAPI 文档。
- 日志。
- Windows/NAS 启动方式。

## 7. 代码审查红线

审查任何后续代码时，必须检查：

- 是否新增手写路由解析。
- 是否循环内 SQL 查询导致 N+1。
- 是否 SQLite 连接缺少 timeout/WAL/busy_timeout。
- 是否直接永久删除客户资料。
- 是否文件系统操作缺少异常处理。
- 是否扫描失败会中断整个项目。
- 是否前端 API 路径被无必要改变。

任一红线命中，不建议合入 `codex/team-trial-auth`。

## 8. 当前已固化规则

### Pydantic Schema

- 所有新增请求体必须使用明确的 Pydantic 模型。
- 请求模型默认继承严格模型，禁止多余字段。
- 禁止为了省事新增 `extra="allow"` 的通用写接口模型。
- 如果前端需要提交新字段，必须同步更新 Schema、业务模块和测试。

### 日志与排错

- FastAPI 请求必须保留统一耗时日志。
- 4xx/5xx 请求需要能从日志中定位 method、path、status、duration。
- 应用日志必须落盘，默认路径为 `data/logs/app.log`，可通过 `CUSTOMER_PROJECT_LOG_DIR` 覆盖。
- 文件系统操作失败必须记录上下文：
  - project_id 或 task_id。
  - 源路径。
  - 目标路径或目标目录。
  - 原始异常。
- 面向前端的错误信息要可读，但日志中要保留完整堆栈，便于排查 NAS/共享盘权限和网络闪断问题。

### 备份与启动

- 默认启动脚本为 `run_server.cmd`。
- FastAPI 明确启动脚本为 `run_fastapi_server.cmd`。
- 数据库备份使用 `POST /api/system/backup`，仅 Admin 可执行。
- 备份目录优先使用 `backup_target_path`，为空时使用 `data/backups`。
- 备份必须使用 SQLite 原生 backup API，不直接复制运行中的数据库文件。
