# 版本管理半自动规则

这个仓库只管理系统代码和说明文档。客户资料、项目文件、SQLite 数据库、日志和缓存不要提交到 GitHub。

## 常用命令

查看当前版本状态：

```powershell
.\tools\version.cmd status
```

保存一次改动并提交：

```powershell
.\tools\version.cmd save -Type feat -Message "add backup button"
```

保存并推送到 GitHub：

```powershell
.\tools\version.cmd save -Type feat -Message "add backup button" -Push
```

开始一个较大的功能分支：

```powershell
.\tools\version.cmd branch -Name backup-system
```

脚本会自动创建：

```text
codex/backup-system
```

发布一个版本标签：

```powershell
.\tools\version.cmd release -Version v0.2.0 -Push
```

## 提交类型

```text
feat      新功能
fix       修复问题
refactor  重构代码
docs      文档
style     界面样式
data      测试数据或模板
chore     配置和杂项
```

## 推荐节奏

小修改可以直接在 `main` 上保存：

```powershell
.\tools\version.cmd save -Type fix -Message "repair project role dropdown" -Push
```

影响较大的功能先开分支：

```powershell
.\tools\version.cmd branch -Name file-import
```

确认功能稳定后，再合并回 `main`。

## 脚本会做什么

- 检查数据库、日志、缓存文件是否被 Git 跟踪。
- 尝试运行 Python 语法编译检查。
- 只暂存代码和文档范围内的文件。
- 自动生成规范提交信息，例如 `feat: add backup button`。
- 可选执行 `git push`。
- 打版本标签前要求工作区干净。

## 仍然需要人工判断的事

- 提交说明写什么。
- 当前改动是 `feat`、`fix` 还是其他类型。
- 是否要打新版本号。
- 是否把较大的功能放到单独分支开发。

原则：让脚本处理重复动作，让人判断业务含义。
