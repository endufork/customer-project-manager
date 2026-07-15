# 文档索引

本文是项目文档入口。后续新增需求、架构、上线、权限、工作流、报表、通知或外部集成文档时，应同步更新本索引。

## 推荐阅读顺序

### 只想运行和试用

1. `README.md`
2. `fastapi-stabilization-runbook-v0.1.md`
3. `team-trial-auth-requirements-v0.1.md`
4. `file-visibility-permission-principles-v0.1.md`

### 准备继续开发

1. `AGENTS.md`
2. `branch-change-management-v0.1.md`
3. `ARCHITECTURE.md`
4. `adversarial-project-review-v0.1.md`
5. `project-management-platform-architecture-plan-v0.1.md`
6. `engineering-workbench-gap-plan-v0.1.md`

### 准备讨论产品方向

1. `PRODUCT.md`
2. `DESIGN.md`
3. `project-management-platform-architecture-plan-v0.1.md`
4. `continuous-optimization-roadmap-v0.1.md`

## 文档效力与冲突处理

| 文档类型 | 作用 | 冲突时的处理规则 |
|---|---|---|
| 当前基线 | `README.md`、`ARCHITECTURE.md`、v0.2 需求文档 | 描述当前已经具备的能力和有效边界，优先于历史方案 |
| 当前计划 | `project-management-platform-architecture-plan-v0.1.md`、各 gap/plan 文档 | 描述尚未完成的下一步；已完成事项应及时移出当前优先级 |
| 决策与审查 | `adversarial-project-review-v0.1.md` | 记录确认结论、实施提交、测试证据和剩余阻塞项 |
| 时间线记录 | `continuous-optimization-roadmap-v0.1.md` | 按日期保留当时决策；同一事项冲突时以日期更晚的章节为准 |
| 历史参考 | v0.1 需求、模型和 SQL 文档 | 仅用于追溯，不作为当前开发或验收依据 |

无法判断时，依次以 `AGENTS.md`、当前 v0.2 需求、`ARCHITECTURE.md`、对抗式审查追踪矩阵为准。

## 当前基线文档

### 项目总览

- `README.md`：当前系统能力、运行方式、验证方式和关键入口。
- `DOCUMENTATION_INDEX.md`：本文档，说明文档地图和维护规则。
- `PRODUCT.md`：产品定位、用户、目标、设计原则。
- `DESIGN.md`：视觉和交互设计系统。

### 架构与代码结构

- `ARCHITECTURE.md`：当前技术架构、后端/前端模块边界、文件安全边界。
- `project-management-platform-architecture-plan-v0.1.md`：整体架构、功能需求、模块边界和实施计划。
- `fastapi-refactor-plan-v0.1.md`：FastAPI 重构计划。
- `fastapi-refactor-checklist-v0.1.md`：FastAPI 重构审查清单。
- `fastapi-stabilization-runbook-v0.1.md`：FastAPI 稳定化、启动、日志、备份和扫描策略。

### 协作、分支和版本

- `AGENTS.md`：项目级开发规则，Codex 和人工开发默认遵守。
- `branch-change-management-v0.1.md`：分支角色、开发流程、修复同步和服务重启规则。
- `VERSIONING.md`：半自动版本管理规则和脚本说明。

### 项目资料库

- `customer-project-management-requirements-v0.2.md`：当前项目资料库需求基线。
- `new-project-entry-spec-v0.2.md`：新项目录入页面、字段规格、标准目录和扫描入口。
- `mvp-data-model-v0.2.md`：当前 MVP 数据模型说明。
- `project-library-bug-log-v0.1.md`：项目库 bug 记录。
- `project-status-link-plan-v0.1.md`：项目库状态与项目执行联动计划。

### 工程执行工作台

- `engineering-workbench-requirements-v0.2.md`：工程工作台需求基线。
- `engineering-workbench-gap-plan-v0.1.md`：工作台闭环、看板、PM 待处理中心和后续 gap。
- `workbench-bug-log-v0.1.md`：工作台 bug 记录。

### 项目看板与 PM 待处理

- `project-board-requirements-v0.1.md`：项目看板需求、场景、字段、权限、验收标准。
- `engineering-workbench-gap-plan-v0.1.md`：记录项目看板、风险总览和 PM 待处理中心实现状态。

### 登录、权限和团队试用

- `team-trial-auth-requirements-v0.1.md`：企业邮箱验证码登录、角色权限、Due Date 审批、通知和上线试用需求。
- `file-visibility-permission-principles-v0.1.md`：文件可见度、角色边界和后续 NAS ACL 落地原则。

### 审查与整改

- `adversarial-project-review-v0.1.md`：项目需求、业务流程、代码安全、开发流程和文档完整性的对抗式审查，以及整改追踪矩阵和待确认决策。

### 部署、备份和运行

- `local-nas-deployment-backup-plan-v0.1.md`：本地 NAS、备份、邮件通知、远程访问和预算讨论结论。
- `fastapi-stabilization-runbook-v0.1.md`：服务启动、日志、数据库备份、扫描策略和测试覆盖。

### 持续计划

- `continuous-optimization-roadmap-v0.1.md`：系统模块后续优化方向和阶段决策记录。

## 历史参考文档

以下文档保留历史讨论脉络，不作为当前优先实现基线：

- `customer-project-management-requirements-v0.1.md`
- `mvp-data-model-v0.1.md`
- `mvp-sqlite-schema-v0.1.sql`
- `new-project-entry-spec-v0.1.md`
- `engineering-workbench-requirements-v0.1.md`

如果历史文档与当前文档冲突，以当前基线文档和 `AGENTS.md` 为准。

## 文档覆盖评估

当前已有充分记录的方面：

- 项目整体对抗式审查、整改分级和团队试用退出条件。
- 项目资料库需求和数据模型。
- 新项目入口。
- 文件夹、扫描、解析和目录安全原则。
- 项目基础信息 `input + datalist` 方向、机械/电气目录分层和当前项目一键扫描范围。
- 工程工作台闭环。
- 风险分层、Due Date 改期、交付物确认。
- 项目看板和跨项目风险总览。
- PM 待处理中心。
- 登录、权限和团队试用。
- FastAPI 重构、日志、备份、扫描策略。
- NAS/局域网部署和备份方向。
- 分支、提交、验证和版本管理规则。

当前仍需继续细化的方面：

- 通知临期/逾期定时策略、保留周期和邮件增强；通知 v1 的数据模型、页面和工作流事件已经实现。
- 报表导出模块的字段、模板和入口。
- BOM 管理和采购系统联动接口。
- 实际团队试用运维清单：运行机器、备份路径、日志保留周期、SMTP 账号。
- 历史未绑定任务的账号补齐规则；新任务和 Engineer 对象权限已经按登录账号绑定。
- 项目库状态联动建议的确认流程。
- NAS 正式试用后的目录 ACL 验证和调整记录。
- 数据库迁移版本、远程 CI 和恢复演练记录。

## 维护规则

- 新增重要功能模块时，至少更新：
  - `DOCUMENTATION_INDEX.md`
  - `project-management-platform-architecture-plan-v0.1.md`
  - 对应模块需求或 gap 文档
- 修改架构、模块边界、权限边界、部署方式时，必须更新：
  - `ARCHITECTURE.md`
  - `AGENTS.md` 中对应规则
  - `continuous-optimization-roadmap-v0.1.md`
- 发现或修复 bug 时，按模块更新：
  - `project-library-bug-log-v0.1.md`
  - `workbench-bug-log-v0.1.md`
- 纯文案、小样式或局部代码整理，如不改变需求和架构，可以不更新架构计划，但应保持 README 和索引不误导。
