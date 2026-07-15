# 分支变动管理办法 v0.1

## 当前结论

本项目已经不再适合把所有修改直接落在旧 `main` 上。`main` 只保留稳定基线；团队试用、权限、工作台、FastAPI 等持续开发，应从当前主工作分支继续推进。

当前推荐主工作分支：

```text
codex/team-trial-auth
```

原因：

- 已包含项目资料库、工程工作台、登录权限、PM/工程师视图。
- 是当前最接近团队试用的完整分支。
- 后续 FastAPI、状态联动、通知、部署自启都应从此分支新开分支，而不是回到旧 `main`。

截至 2026-07-15，当前唯一待集成的推进分支是：

```text
main
└─ codex/team-trial-auth
   └─ codex/adversarial-remediation
```

- `main` 是 `codex/team-trial-auth` 的直接祖先。
- `codex/adversarial-remediation` 是 `codex/team-trial-auth` 的线性后继，包含 17 个已按类别拆分的整改与文档提交，以及本次分支治理文档提交。
- 当前推进分支先合入 `codex/team-trial-auth`；完成真实 NAS ACL、恢复演练和 C-12 运维参数确认后，集成分支才允许合入 `main`。

## 分支角色

```text
main
```

稳定基线。只接收已经验证过、需要成为长期基础能力的改动。不要直接在 `main` 上做工作台、权限、FastAPI、团队上线等大改。

```text
codex/team-trial-auth
```

当前集成分支。承载团队试用版本，作为后续新功能分支的起点。

```text
codex/feature-name
```

功能分支。从 `codex/team-trial-auth` 拉出，用于单项功能开发，例如：

```text
codex/fastapi-refactor
codex/project-status-link
codex/startup-service
codex/notification-center
```

当前 `codex/adversarial-remediation` 属于这一类功能/整改分支，不取代 `codex/team-trial-auth` 的长期集成分支角色。

## 2026-07-15 分支盘点

| 分支 | 与集成线关系 | 处理结论 |
|---|---|---|
| `main` | 集成分支包含其全部提交，当前落后 57 个提交 | 保持稳定，团队试用退出条件满足前不合并 |
| `codex/team-trial-auth` | 与远端同步 | 唯一集成分支 |
| `codex/adversarial-remediation` | 从集成分支线性前进 | 推送并通过 PR 合入集成分支 |
| `codex/file-visibility-permissions` | 全部提交已包含在整改分支 | 不单独推送或合并；主线落地后删除本地分支 |
| `codex/project-board-v1` | 已完整包含在集成分支 | 不再推送；主线落地后删除本地分支 |
| `codex/user-bound-tasks-admin-delete` | 与集成分支指向同一提交 | 重复分支，主线落地后删除本地和远端分支 |
| `codex/fastapi-refactor`、`codex/pm-action-center`、`codex/workbench-closure-flow` | 已完整包含在集成分支 | 仅保留历史追溯，主线落地后归档/删除 |
| `codex/backend-module-split` | 与集成分支分叉，独有旧 `server.py` 拆分提交 | 已被后续 FastAPI 架构取代，不整体合并 |
| `codex/engineering-workbench-mvp`、`codex/workbench-backend-split`、`codex/workbench-frontend-split` | 各自保留一个旧扫描同步提交 | 扫描修复已通过 `main` 的 `02dffee` 进入集成线，不整体合并 |

历史分支不能仅因存在“独有提交”就直接合并。必须先判断该提交是否已经被后续架构替代、通过另一提交进入主线，或只适用于旧目录结构。

## 开发流程

1. 先确认当前分支：

```powershell
git status --short --branch
```

2. 大功能从 `codex/team-trial-auth` 新开分支。
3. 一个分支只做一类事情。
4. 完成后先合回 `codex/team-trial-auth`。
5. 试用稳定后，再决定是否合入 `main`。

### 推送与 PR 规则

1. 功能分支第一次推送时设置同名上游分支。
2. 功能分支通过 PR 合入 `codex/team-trial-auth`，不直接推送集成分支。
3. 当前仓库的整改追踪矩阵引用具体 commit hash；合并时保留原提交，不使用 squash 或 rebase merge。
4. PR 合并后在集成分支重新运行 `tools/check.cmd` 和 Playwright E2E。
5. `codex/team-trial-auth` 合入 `main` 必须使用独立 PR，并检查团队试用退出条件。
6. 未满足 NAS ACL、数据库恢复演练、正式运行和维护责任人等阻塞条件时，不提前合入 `main`。

### 历史分支清理规则

- 先完成推进分支 → 集成分支 → `main` 的合并和验证，再删除历史分支。
- 已被集成分支完整包含或与集成分支指向相同提交的分支可以直接列入清理清单。
- 与集成分支分叉的旧分支先记录独有提交为何不再需要，再归档或删除。
- 删除远端分支前，应确认没有未关闭 PR、发布流程或外部部署仍引用该分支。
- 不使用历史分支作为新功能起点；需要参考时只查看提交或文件差异。

## 修复类改动

如果是所有版本都需要的底层 bug，例如文件扫描同步、数据库迁移、目录安全逻辑：

- 优先在当前主工作分支 `codex/team-trial-auth` 修复和验证。
- 再用同一个核心文件或同一个 commit 同步到需要保留的分支。
- 最后再决定是否合入 `main`。

不要先在旧 `main` 修改，再反向合入所有功能分支；这样容易和已经拆分过的前端/后端结构冲突。

## FastAPI 重构分支（历史状态）

FastAPI 重构曾使用独立分支：

```text
codex/fastapi-refactor
```

该分支已经完整进入 `codex/team-trial-auth`，不再作为后续开发起点。以下迁移顺序仅保留为历史记录：

1. 保留现有业务模块，不重写业务逻辑。
2. 先用 FastAPI 替换 HTTP 路由层。
3. 保持现有 API 路径不变，前端先不动。
4. 再迁移认证、文件上传、静态资源。
5. 最后补 OpenAPI 文档和部署方式。

## 项目状态联动分支

项目库状态和项目执行状态联动也应单独开分支：

```text
codex/project-status-link
```

原则：

- 项目库状态记录项目事实。
- 工作台任务状态记录执行过程。
- 联动应是“摘要和建议状态”，不要让任务状态随意覆盖项目库状态。
- PM 确认关键节点后，才能推动项目库状态变化。

## 本地服务和重启

当前系统是本地临时 Web 服务。电脑重启、休眠、终端关闭后，`http://127.0.0.1:8765` 会进不去，因为服务进程已经停止。

短期：

```powershell
run_server.cmd
```

中期：

- 做 Windows 开机自启脚本。
- 或部署到 NAS/局域网服务器。

团队试用阶段推荐不要依赖个人电脑长期开机，应部署到 NAS 或一台固定 Windows 主机。
