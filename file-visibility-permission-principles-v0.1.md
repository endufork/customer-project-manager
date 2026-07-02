# 文件可见度与 NAS ACL 权限原则 v0.1

本文记录 2026-07-02 对项目资料文件权限的阶段性结论。当前先在系统中落地可见度元数据和后端接口过滤；NAS / Windows ACL 需要等正式在 NAS 上试用后按真实共享目录再配置。

## 1. 当前结论

- 不设置 `Readonly` 业务角色。团队规模不大，当前只保留 `Admin`、`PM`、`Engineer`。
- 新用户首次获取验证码后进入 `pending` 状态，由 Admin 分配角色并启用。
- 管理台前端只用于查看和维护账号、状态和角色；真实文件保护不能只靠前端隐藏入口。
- 当前系统先做后端文件索引可见度过滤；最终直接浏览共享目录时的保护必须依赖 NAS / Windows ACL。
- 内部报价对工程师开放，因为工程师需要参与方案、成本和报价输入。

## 2. 角色边界

| 角色 | 文件视角 | 主要职责 |
| --- | --- | --- |
| Admin | 全部文件 | 系统设置、用户管理、删除/恢复、备份和权限配置 |
| PM | 工程文件、内部报价、对客报价、PO | 项目事实维护、客户报价/PO、任务分配、交付确认 |
| Engineer | 工程文件、内部报价、图纸模型、交付资料 | 技术方案、设计、BOM/估算输入、任务执行和交付 |

`pending` 和 `disabled` 是账号状态，不是业务角色。

## 3. 文件可见度

系统内文件记录使用三类可见度：

| 可见度 | 可见角色 | 用途 |
| --- | --- | --- |
| `engineering` | Admin、PM、Engineer | 默认工程资料、内部报价、图纸模型、验收交付 |
| `pm_only` | Admin、PM | 对客报价、客户 PO、后续采购商务或供应商报价 |
| `admin_only` | Admin | 预留给系统备份、敏感配置或特殊管理文件 |

当前默认分类：

| 文件类别 | 默认可见度 |
| --- | --- |
| 询价需求 | `engineering` |
| 方案资料 | `engineering` |
| 内部报价 | `engineering` |
| 客户报价 | `pm_only` |
| PO 订单 | `pm_only` |
| 图纸模型 | `engineering` |
| 验收发货 | `engineering` |
| 沟通记录 | `engineering` |
| 其他 | `engineering` |

## 4. 建议 NAS 目录权限

正式 NAS 试用时，建议把报价与订单目录拆细，便于 ACL 落地：

```text
项目文件夹
  01_输入资料                         Engineer / PM
  02_报价与订单
    01_内部报价                       Engineer / PM
    02_对客报价                       PM
    03_PO订单                         PM
  03_方案与图纸                       Engineer / PM
  04_BOM与采购
    01_BOM                            Engineer / PM
    02_采购商务                       PM
  05_装配调试                         Engineer / PM
  06_验收发货                         Engineer / PM
  99_其他                             默认 Engineer / PM，特殊文件单独调整
```

## 5. 当前已落地范围

- `file_categories.default_visibility` 保存文件类别默认可见度。
- `file_categories.default_folder` 已改为细分落盘目录，例如内部报价、对客报价和 PO 分别进入不同子目录。
- `project_files.visibility_code` 和 `project_group_files.visibility_code` 保存具体文件记录可见度。
- 项目详情接口按登录用户角色过滤文件列表。
- 文件导入、目录扫描、工作台交付上传会写入默认可见度。
- 新项目会创建细分后的标准目录结构。
- 新上传/导入文件会按文件类别进入细分目录。
- 旧项目可使用 `tools/restructure_project_folders.py` 先 dry-run 再显式 `--apply` 迁移。
- 历史 `readonly` 用户迁移为 `pending` 并清理 `readonly` 角色。

## 6. 暂不做

- 暂不在本地模拟完整 NAS ACL。
- 暂不做复杂只读角色。
- 暂不做每个文件的前端手工改权限界面；后续等 NAS 目录和真实使用习惯确认后再决定。
- 当前 `打开文件夹` 是本机/NAS 便利入口，不能替代 ACL。只要用户在共享目录层面有直接访问权限，就可能绕过系统前端和 API。

## 7. 后续验证项

- 在 NAS 上创建试用共享目录和测试用户组。
- 用 Engineer / PM / Admin 三类账号分别验证直接浏览共享目录和系统内项目详情。
- 确认报价、PO、采购商务目录是否需要进一步拆分。
- 确认是否需要文件级例外权限，还是目录级 ACL 已足够。
