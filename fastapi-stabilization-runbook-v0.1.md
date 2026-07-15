# FastAPI 稳定化与试用运维说明 v0.1

## 1. 目的

本文记录当前 FastAPI 收尾后的基础运维方式，用于本地开发、局域网试用和后续 review。

## 2. 服务启动方式

默认启动：

```powershell
run_server.cmd
```

明确 FastAPI 启动：

```powershell
run_fastapi_server.cmd
```

底层脚本：

```powershell
tools\start-fastapi-server.ps1
```

默认访问地址：

```text
http://127.0.0.1:8765/
```

可选环境变量：

```text
CUSTOMER_PROJECT_PORT
CUSTOMER_PROJECT_PYTHON
CUSTOMER_PROJECT_DATA_DIR
CUSTOMER_PROJECT_DB_PATH
CUSTOMER_PROJECT_LOG_DIR
CUSTOMER_PROJECT_LOG_LEVEL
```

环境模式与认证配置：

```text
CUSTOMER_PROJECT_ENV=development | test | production
CUSTOMER_AUTH_SECRET
CUSTOMER_SMTP_HOST
CUSTOMER_SMTP_FROM_EMAIL
CUSTOMER_SMTP_USERNAME
CUSTOMER_SMTP_PASSWORD
```

- `tools/start-fastapi-server.ps1` 在未设置环境模式时使用 `development`，只监听本机回环地址。
- 正式部署必须显式设置 `production`、至少 32 字符的随机认证密钥和完整 SMTP 配置。
- 生产配置不完整时应用启动失败，不允许降级返回测试验证码。
- 生产环境关闭 FastAPI API 文档，并启用 CSP、禁止 iframe、MIME 嗅探和 Referrer 限制等基础响应头。

### 上传与解析限制

- `CUSTOMER_UPLOAD_MAX_MB`：单文件上限，默认 `500`。
- `CUSTOMER_PARSER_MAX_MB`：PDF、DOCX、XLSX 和文本的解析上限，默认 `25`；超过后仍归档，但不解析正文。
- `CUSTOMER_UPLOAD_CHUNK_MB`：流式写入分块大小，默认 `1`。
- `CUSTOMER_UPLOAD_ALLOWED_EXTENSIONS`：逗号分隔允许扩展名。默认拒绝 EXE、脚本和未知类型；压缩包只保存，不自动解压；3D 模型不做正文解析。
- 超限上传返回 HTTP 413，不允许的类型返回 HTTP 415；失败时删除尚未完成的目标文件，不写数据库记录。

## 3. 日志落盘

应用日志默认写入：

```text
data/logs/app.log
```

可用环境变量覆盖：

```powershell
$env:CUSTOMER_PROJECT_LOG_DIR = "D:\ProjectManagerLogs"
```

日志策略：

- 使用滚动日志。
- 单个日志文件上限 5 MB。
- 最多保留 10 个历史文件。
- API 请求日志包含 method、path、status、duration。
- 文件系统异常日志包含项目/任务、源路径、目标路径和原始异常。

## 4. 数据库备份

备份目录优先使用系统设置：

```text
backup_target_path
```

如果未配置，则默认使用：

```text
data/backups
```

手动触发备份 API：

```http
POST /api/system/backup
```

权限要求：

```text
Admin
```

备份方式：

- 使用 SQLite 原生 backup API。
- 不直接复制运行中的数据库文件。
- 备份文件命名包含时间戳。

后续团队试用前应确认：

- 备份目录放本机、移动硬盘、NAS 还是网盘同步目录。
- 备份周期。
- 是否需要 Windows 计划任务定时调用备份。

## 5. 扫描策略

当前扫描保持轻量：

- 不做实时监听。
- 不做消息队列或跨机器扫描调度；全局扫描使用单进程后台任务。
- 保留项目级手动扫描。
- 保留共享资料手动扫描。
- 保留项目详情“一键扫描”，范围仅为当前项目文件夹和其关联的 `00_共享资料`。
- 保留 Admin 后台全局扫描，用于扫描全部有效项目文件夹和共享资料层，并提供持久化进度查询。

扫描优先级：

```text
准确性
安全性
可排错
性能优化
```

当前行为：

- 新文件写入数据库索引。
- 已变化文件更新数据库索引。
- 物理文件缺失时移除数据库旧索引。
- 不删除任何物理客户资料。
- 单个文件失败不会中断整个扫描。
- 扫描结果包含 `failed_files` 和 `file_errors`。
- 项目详情一键扫描不会扫描全库。
- Admin 全局扫描只更新文件索引，不创建、移动或删除物理客户文件；如果文件索引指向的物理文件已不存在，会移除旧索引记录。
- Admin 全局扫描先读取待扫描范围，再按单个项目或单个共享目录开启和提交短事务；一个范围失败不会回滚已经完成的其他范围，也不会在全库扫描期间持续占用同一个 SQLite 写事务。
- `POST /api/system/global-scan` 创建任务并返回 `202`；`GET /api/system/global-scan/{job_id}` 查询进度，`GET /api/system/global-scan` 返回最近任务。
- 同一时间只允许一个 `pending` / `running` 任务；重复点击复用当前任务。服务重启时未完成任务标记为失败，避免任务永久停留在运行中。

## 6. 当前测试覆盖

提交前检查：

```powershell
.\tools\check.cmd
```

当前覆盖：

- FastAPI 健康检查。
- 登录验证码开发流。
- 受保护接口未登录返回 401。
- Pydantic 严格 Schema 额外字段返回 422。
- 工作台列表聚合摘要。
- 数据库备份 API。
- 日志落盘。
- 扫描单文件失败不中断。
- 全局扫描按项目/共享目录使用独立数据库连接和短事务。
- 后台扫描任务创建、进度轮询、最终结果和重复任务保护。
- Playwright 测试数据库、项目目录和端口与正常运行环境隔离。

## 7. 后续建议

- 增加 Windows 开机自启。
- 增加定时数据库备份。
- 增加 Admin 页面查看最近备份和日志状态。
- 增加更多工作台写接口测试。
- 团队试用前确认 NAS/共享盘权限。
