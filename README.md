# 项目管理系统

面向非标设备制造团队的局域网项目管理工具。系统把客户项目资料库、工程执行工作台、项目看板、文件归档索引、权限和审计连接起来，核心目标是让项目事实和执行过程形成闭环。

当前团队试用集成主分支：

```text
codex/team-trial-auth
```

当前开发形态：

```text
FastAPI + SQLite WAL + 本地/NAS 文件目录 + Web 前端
```

## 当前能力

### 项目资料库

- 新建项目并自动生成 INQ 号。
- 后续补 WO号/内部设备号；已有 WO 时界面优先显示 WO。
- 支持客户集团、法人主体、工厂/站点、客户产品/生产线、联系人。
- 一条项目记录对应一台设备、夹具、改造或其他具体工程对象。
- 产品/产线共用资料放在共享资料层。
- 支持项目文件夹生成、打开、扫描、目录迁移和文件索引。
- 支持项目库列选择、排序、搜索和执行摘要。

### 工程执行工作台

- 从项目资料库进入单项目执行。
- PM 创建任务并分配负责人、Due Date、是否需要交付文件。
- 工程师处理任务、上传交付文件、提交完成说明、申请改期、创建或解决风险。
- 文件型任务闭环：

```text
工程师上传文件
→ 自动归档到资料库
→ PM 确认或驳回
→ 任务关闭或返工
```

- 无文件任务闭环：

```text
提交完成说明
→ PM 确认关闭或驳回返工
```

- 阻塞任务可自动生成或关联任务级风险。
- 风险支持产品/产线级、设备/WO级、任务级。

### 项目看板

- 面向所有登录用户的项目总览。
- 聚合项目事实和执行摘要。
- 默认突出超期、阻塞、高风险、待确认、本周到期、责任人和下一步动作。
- 支持项目总览和跨项目风险总览。
- 可从快照跳转到项目执行。

### PM 待处理中心

- PM/Admin 可见的集中处理页。
- 聚合：
  - 待确认交付文件。
  - 待确认完成说明。
  - 待审批 Due Date 改期。
  - 待确认风险关闭。
- 处理后事项自动移出队列。

### 登录与权限

- 企业邮箱验证码登录。
- 当前允许域名：`jinxiangsz.com`。
- 新用户默认进入待分配状态，Admin 分配角色并启用后才能登录。
- 角色：Admin、PM、Engineer。
- 权限必须由后端校验，前端隐藏按钮只是辅助。
- 文件可见度当前由后端文件索引过滤，最终共享目录保护等 NAS 试用时用 ACL 落地。

## 本地运行

开发和测试环境安装依赖：

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
npm ci
```

仅运行服务时可以只安装 `requirements.txt`。显式设置的 `CUSTOMER_PROJECT_PYTHON` 优先级最高；未设置时，启动和检查脚本优先使用仓库内 `.venv`，再回退到 Codex 内置运行时或系统 Python。

启动服务：

```bat
run_server.cmd
```

本地启动脚本会在未显式设置时使用 `CUSTOMER_PROJECT_ENV=development`，允许在 SMTP 未配置时显示测试验证码。正式环境必须显式设置：

```text
CUSTOMER_PROJECT_ENV=production
CUSTOMER_AUTH_SECRET=至少32字符的随机值
CUSTOMER_SMTP_HOST
CUSTOMER_SMTP_FROM_EMAIL
CUSTOMER_SMTP_USERNAME
CUSTOMER_SMTP_PASSWORD
```

生产环境缺少认证密钥或 SMTP 时服务拒绝启动，且验证码接口绝不返回 `dev_code`。生产环境默认关闭 `/docs`、`/redoc` 和 `/openapi.json`。

上传策略可通过环境变量调整：`CUSTOMER_UPLOAD_MAX_MB` 默认 500 MB，`CUSTOMER_PARSER_MAX_MB` 默认 25 MB，`CUSTOMER_UPLOAD_CHUNK_MB` 默认 1 MB。`CUSTOMER_UPLOAD_ALLOWED_EXTENSIONS` 使用逗号分隔扩展名；默认允许常见工程文档、图片、压缩归档和 CAD/3D 格式，拒绝可执行文件、脚本和未知扩展名。压缩包只归档不解压，大于解析阈值的文档及 3D 模型只归档和索引元数据。

访问地址：

```text
http://127.0.0.1:8765/
```

本地数据库默认生成在：

```text
data\customer_projects.db
```

不要把 `data/`、客户资料、日志、缓存提交到 Git。

## 验证

提交前运行：

```powershell
.\tools\check.cmd
```

前端关键交互验证：

```powershell
npm run test:e2e
```

## 依赖维护

- `requirements.in`：Python 直接运行依赖及兼容范围。
- `requirements-dev.in`：Python 直接开发、测试依赖及兼容范围。
- `requirements.txt`：Windows / Python 3.12 完整运行依赖锁。
- `requirements-dev.txt`：在运行依赖锁基础上补充完整测试依赖锁。
- `package-lock.json`：Node / Playwright 依赖锁；安装时使用 `npm ci`。
- `.venv`：本机隔离 Python 环境，不进入 Git；未显式指定 Python 时启动脚本会自动优先使用。

更新 Python 版本范围后重新解析锁文件：

```powershell
.\tools\lock-dependencies.cmd
```

锁文件必须和相关代码一起提交；不要只修改 `.in` 文件。

修改后端、前端、API 或静态资源后，应重启本地服务：

```powershell
.\run_server.cmd
```

## 代码结构

```text
app.py                         本地兼容启动入口
customer_m/fastapi_app.py      FastAPI 应用入口
customer_m/api/                HTTP 路由、请求校验、权限依赖、响应组织
customer_m/modules/            后端业务模块
static/index.html              单页应用 HTML
static/app.js                  前端启动和全局事件
static/js/                     前端功能模块
static/styles.css              当前集中样式文件
tests/                         Python 与 Playwright 测试
tools/                         检查、运行、版本辅助脚本
```

## 关键文档

完整文档入口见：

```text
DOCUMENTATION_INDEX.md
```

当前最重要的文档：

- `AGENTS.md`：项目协作、分支、提交、验证和开发规则。
- `project-management-platform-architecture-plan-v0.1.md`：整体架构、模块边界、功能需求和实施计划。
- `engineering-workbench-gap-plan-v0.1.md`：工作台闭环、看板、PM 待处理中心和后续 gap。
- `project-board-requirements-v0.1.md`：项目看板需求。
- `team-trial-auth-requirements-v0.1.md`：登录、权限和团队试用要求。
- `fastapi-stabilization-runbook-v0.1.md`：启动、日志、备份、扫描和测试说明。
- `branch-change-management-v0.1.md`：分支变动管理办法。
- `VERSIONING.md`：版本管理半自动规则。

## 当前下一步

短期优先级：

1. 收口 Engineer 对象级授权，历史未绑定任务暂只允许 PM 写入。
2. 收紧上传大小、类型和文档解析资源限制。
3. LAN 文件夹入口改为复制 UNC 路径。
4. 按角色设置默认首页，并做系统内通知和未读计数。
5. 做项目库状态联动建议：工作台生成建议状态，PM 确认后应用。
6. 团队试用前确认正式运行、SMTP、备份和恢复参数。

暂不优先做：

- 复杂实时文件监听。
- 复杂甘特图或排产。
- 结构化报价/PO 管理、独立待办和 Excel/CSV 导出。
- 深度采购系统写入。
- 高级统计大屏。
- 完整移动端。
