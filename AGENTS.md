# 项目协作与版本管理规则

本文件是本仓库的项目级工作规则。以后在本项目中使用 Codex 或手动开发时，默认遵守这些规则。

## 分支规则

- `main` 代表当前可用、相对稳定的版本。
- 小修小补可以直接在 `main` 上提交，例如文案、轻量 bug、文档补充。
- 新功能、较大结构调整、实验方向使用 `codex/*` 分支。
- 分支命名示例：

```text
codex/engineering-workbench
codex/excel-export
codex/backup-settings
```

## 提交规则

- 每次 commit 只做一类事情。
- 提交信息使用：

```text
feat: 新功能
fix: 修复问题
docs: 文档
refactor: 重构
style: 界面样式
data: 测试数据或模板
chore: 配置和杂项
```

- 好的提交示例：

```text
feat: add project column picker
fix: clean stale project folders
docs: add engineering workbench requirements
```

## 推送与 PR 规则

- `push` 只是上传到 GitHub，不等于业务确认完成。
- 大功能分支建议通过 PR 合并回 `main`。
- PR 合并前至少确认：
  - 页面能打开。
  - 相关 API 正常。
  - `tools/check.cmd` 通过。
  - 没有客户资料、数据库、日志、缓存进入 Git。

## 自动检查

提交前应运行：

```powershell
.\tools\check.cmd
```

本仓库支持 Git pre-commit hook。安装后，每次 `git commit` 前会自动运行检查：

```powershell
.\tools\install-hooks.cmd
```

## 禁止提交

不要提交：

```text
data/customer_projects.db
D:\01_CustomerProject
客户报价、PO、图纸、模型等真实项目资料
server.log
server.err
server.pid
__pycache__
*.pyc
```

## 当前业务约定

- 项目资料库的一条项目对应一台设备、夹具、改造或其他具体工程对象。
- INQ号用于前期工程支持。
- WO号/内部设备号用于正式工程执行。
- 项目库显示当前编号：已有 WO 时显示 WO，未开 WO 时显示 INQ。
- 多台设备共用资料放在客户产品/生产线共享资料层。

## 持续优化与讨论规则

- 后续模块优化方向、讨论结论和阶段计划持续记录在：

```text
continuous-optimization-roadmap-v0.1.md
```

- 每次围绕系统方向、模块边界、权限、工作流、上线部署等形成明确结论后，应更新该文件。
- 讨论结论需要尽量写清楚：
  - 决策内容
  - 适用模块
  - 暂不做的内容
  - 下一步动作
  - 未确认信息
- 新增功能优先确认闭环，不只增加入口。每个新增功能都要回答：

```text
谁使用？
在哪个页面进入？
会改变什么状态？
谁确认？
是否写日志？
是否产生通知？
是否归档到资料库？
```

- 项目资料库负责“项目事实”，项目执行工作台负责“执行过程”，不要把两类职责混在一起。
- UI 优化默认以减轻工程师和 PM 负担为目标，优先展示“下一步该做什么”和“哪里需要处理”。
- 大功能仍使用 `codex/*` 分支讨论和实现；主分支只承载稳定版本、文档补充和轻量维护。
