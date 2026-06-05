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

## 开发流程

1. 先确认当前分支：

```powershell
git status --short --branch
```

2. 大功能从 `codex/team-trial-auth` 新开分支。
3. 一个分支只做一类事情。
4. 完成后先合回 `codex/team-trial-auth`。
5. 试用稳定后，再决定是否合入 `main`。

## 修复类改动

如果是所有版本都需要的底层 bug，例如文件扫描同步、数据库迁移、目录安全逻辑：

- 优先在当前主工作分支 `codex/team-trial-auth` 修复和验证。
- 再用同一个核心文件或同一个 commit 同步到需要保留的分支。
- 最后再决定是否合入 `main`。

不要先在旧 `main` 修改，再反向合入所有功能分支；这样容易和已经拆分过的前端/后端结构冲突。

## FastAPI 重构分支

FastAPI 重构必须单独开分支：

```text
codex/fastapi-refactor
```

迁移顺序：

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
