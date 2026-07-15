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
- 不做复杂扫描调度。
- 保留项目级手动扫描。
- 保留共享资料手动扫描。
- 保留项目详情“一键扫描”，范围仅为当前项目文件夹和其关联的 `00_共享资料`。
- 保留 Admin 全局扫描，用于扫描全部有效项目文件夹和共享资料层。

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
- Playwright 测试数据库、项目目录和端口与正常运行环境隔离。

## 7. 后续建议

- 增加 Windows 开机自启。
- 增加定时数据库备份。
- 增加 Admin 页面查看最近备份和日志状态。
- 增加更多工作台写接口测试。
- 团队试用前确认 NAS/共享盘权限。
