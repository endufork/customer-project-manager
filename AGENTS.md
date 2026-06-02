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
