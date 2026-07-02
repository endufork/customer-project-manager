# 系统架构说明

当前系统采用“模块化单体”架构：一个 FastAPI 服务、一个 SQLite 数据库、一套本地/NAS 文件目录、一套 Web 前端。短期目标是支撑 25 人左右团队内网试用，优先保证业务闭环、文件安全、权限边界和可排错能力。

## 总体结构

```text
Web 前端
→ FastAPI API 网关
→ 业务模块
→ SQLite 数据库
→ 本地盘 / NAS / 共享盘文件目录
```

核心边界：

- 项目资料库记录项目事实。
- 工程执行工作台记录执行过程。
- 项目看板和 PM 待处理中心做跨项目聚合。
- 文件系统保存真实客户资料。
- 数据库保存项目、任务、风险、文件索引和审批记录。

## 启动与入口

```text
app.py
customer_m/fastapi_app.py
run_server.cmd
run_fastapi_server.cmd
```

- `app.py` 是兼容启动入口，当前指向 FastAPI 服务。
- `customer_m/fastapi_app.py` 负责创建应用、注册 API 路由、挂载静态资源、初始化数据库。
- `run_server.cmd` 是默认本地启动脚本。

## API 层

```text
customer_m/api/
```

职责：

- 声明式 FastAPI 路由。
- Pydantic 请求体校验。
- 权限依赖。
- 响应组织。
- 将业务动作转发给 `customer_m/modules/`。

当前主要文件：

- `auth.py`：登录、验证码、当前用户、用户管理。
- `bootstrap.py`：前端启动所需下拉数据和配置。
- `projects.py`：项目资料库 CRUD、扫描、打开文件夹、目录重命名。
- `workbench.py`：工程工作台、任务、交付物、风险、Due Date、看板、PM 待处理。
- `system.py`：健康检查、设置、备份等系统接口。
- `schemas.py`：Pydantic 请求和响应模型。
- `deps.py`：当前用户、权限、查询参数辅助。

规则：

- API 文件不承载业务细节。
- 写接口必须使用明确 Schema。
- 权限不能只依赖前端隐藏按钮。
- 角色按后端 `roles` 精确校验；`Admin` 不隐式继承 `PM` 或 `Engineer` 权限。

## 数据层

```text
customer_m/database.py
customer_m/config.py
customer_m/utils.py
```

- `database.py` 管理 SQLite 连接、WAL、busy timeout、初始化和迁移。
- `config.py` 管理项目状态、目录名、文件分类、枚举和默认配置。
- `utils.py` 管理 ID、时间、文本等通用工具。

SQLite 当前仍是合理选择，但团队试用必须保持：

- WAL 模式。
- 合理连接 timeout。
- FastAPI 请求级连接由 `get_db` 统一关闭；SQLite 连接允许跨线程使用，以适配依赖注入和同步路由的线程调度。
- 禁止直接永久删除客户资料。
- 备份位置和周期明确。

## 业务模块

```text
customer_m/modules/
```

### 项目资料库

- `customers.py`：客户集团、法人主体、工厂、联系人创建和复用。
- `projects.py`：项目模块门面。
- `project_rules.py`：WO号/内部设备号、项目性质等规则。
- `project_queries.py`：项目列表、详情、路径、执行摘要查询。
- `project_commands.py`：项目创建、修改、删除、扫描、目录迁移流程。
- `lookups.py`：前端下拉、设置、状态、币种等基础数据。
- `lifecycle.py`：INQ 号、项目事件、状态辅助。

### 文件与目录

- `folders.py`：目录创建、迁移、回收站归档和删除保护。
- `file_types.py`：文件类型和业务分类判断。
- `file_import.py`：散乱文件/上传文件导入标准目录。
- `scanner.py`：项目目录和共享资料差异扫描。
- `parsers.py`：Word、Excel、PDF、TXT、CSV 文本提取。

### 工程执行工作台

- `workbench.py`：工作台业务门面。
- `workbench_common.py`：工作台通用状态、日期、摘要、日志辅助。
- `workbench_queries.py`：执行项目、任务、我的待办、项目详情查询。
- `workbench_tasks.py`：任务创建、修改、删除、完成说明提交和确认。
- `workbench_deliverables.py`：交付文件上传、归档、确认、驳回。
- `workbench_due_dates.py`：Due Date 改期申请、审批和历史。
- `workbench_issues.py`：风险创建、修改、解决、关闭、退回。
- `workbench_board.py`：项目看板聚合查询。
- `workbench_risk_overview.py`：跨项目风险总览。
- `workbench_pm_inbox.py`：PM 待处理中心聚合。

### 权限与运维

- `auth.py`：用户、角色、验证码、会话。
- `system_maintenance.py`：备份、系统维护能力。

认证和角色边界：

- 初始管理员邮箱会自动获得 `Admin + PM`，避免系统冷启动后无人分配角色。
- 新用户默认进入 `pending` 状态，由 Admin 显式分配 `Admin`、`PM` 或 `Engineer` 角色并启用。
- 当前不保留独立 `Readonly` 业务角色，避免小团队试用阶段权限模型过度复杂。
- 验证码错误次数必须在失败路径落库，达到上限后阻断继续尝试。
- SMTP 发信失败记录日志并降级处理，不能让登录验证码接口直接崩溃。

## 前端结构

```text
static/index.html
static/app.js
static/js/
static/css/
static/styles.css
```

当前前端仍是原生单页应用，但已按功能拆分 JS：

- `app-core.js`：全局状态、API 封装、基础工具。
- `auth.js`：登录、权限、用户管理。
- `project-library.js`：项目库入口壳层、页面切换、启动数据加载。
- `project-library-format.js`：项目编号、标记、状态日期、下拉选项等格式化辅助。
- `project-library-list.js`：项目库列配置、筛选排序、KPI 和列表渲染。
- `project-library-detail.js`：项目详情抽屉、编辑、扫描、删除和跳转操作。
- `workbench-view.js`：项目执行主视图。
- `workbench-tasks.js`：任务创建、编辑、完成说明。
- `workbench-deliverables.js`：交付文件上传和确认。
- `workbench-due-dates.js`：Due Date 改期。
- `workbench-risks.js`：风险窗口和风险闭环。
- `workbench-board.js`：项目看板和风险总览。
- `pm-inbox.js`：PM 待处理中心。
- `form-utils.js`、`ui-shell.js`、`workbench-utils.js`、`project-config.js`、`workbench-config.js`：通用辅助和配置。

前端只按 `roles` 判断入口显示和操作能力；同时具备 `PM` 与 `Engineer` 的用户可切换工作台视角。

CSS 已按页面和职责拆到 `static/css/`：

- `tokens.css`：颜色、基础变量。
- `auth-admin.css`：登录、用户管理、角色选择。
- `base-layout.css`：全局壳层、表单、按钮、项目库、通用标签和工具样式。
- `board-inbox.css`：项目看板、风险总览、PM 待处理中心。
- `workbench.css`：项目执行工作台、任务、风险、交付物、Due Date、日志抽屉。
- `overlays-feedback.css`：详情抽屉、toast、确认弹窗。
- `responsive.css`：移动端和窄屏适配。

`static/styles.css` 保留为兼容入口，只通过 `@import` 引入上述模块。新增样式优先进入对应模块，不再继续堆进单个大文件。

## 测试结构

```text
tests/
```

当前覆盖：

- FastAPI smoke 和稳定化。
- 项目搜索和项目目录流转。
- 工作台任务、交付物、Due Date、风险、PM 待处理。
- 项目看板和跨项目风险总览 Playwright 冒烟。

常用验证：

```powershell
.\tools\check.cmd
npm run test:e2e
```

## 文件安全边界

文件系统操作必须遵守：

- 禁止直接永久删除客户资料。
- 删除项目资料必须进入系统回收站或保留原文件。
- 扫描只更新数据库索引，不删除物理文件。
- 目录迁移必须同步数据库路径。
- 文件记录按 `engineering`、`pm_only`、`admin_only` 做后端可见度过滤；内部报价默认工程师可见，客户报价和 PO 默认 PM 可见。
- 后端过滤只能保护系统 API 和页面；直接浏览 NAS/共享盘必须依赖 NAS / Windows ACL，正式试用时再按真实目录落地。
- NAS、UNC、权限不足、文件占用等异常必须记录日志并返回可读错误。

## 后续架构方向

短期：

- 我的任务绑定登录账号。
- 系统内通知。
- 项目库状态联动建议。
- 报表导出。
- 备份和团队试用运维。

中期：

- 通知中心模块。
- 报表模块。
- BOM 管理模块。
- SMTP 邮件提醒。

暂不优先：

- 微服务。
- 消息队列。
- 复杂实时文件监听。
- 大型数据库迁移。
- 采购系统深度写入。
