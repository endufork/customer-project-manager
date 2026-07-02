# 客户项目资料管理系统 MVP 数据模型 v0.2

## 1. 本版变化

本版本基于最新确认信息调整：

- 项目早期可能没有 WO号/内部设备号。
- WO号/内部设备号可能包含英文字母、数字、横杠 `-`、下划线 `_`。
- 币种至少需要支持人民币 `CNY` 和美元 `USD`。
- 新项目文件根目录初步定为 `D:\01_CustomerProject`。
- 备份目录暂未确定，后续可配置为移动硬盘、NAS 或网盘同步目录。
- 第一阶段先做本地 Web 原型，后续可封装为桌面软件。
- 支持客户集团、法人主体、工厂/站点、部门/业务单元层级。
- 支持客户产品/生产线及共享资料。
- 项目需求来源与 PO/采购主体可以分开记录。
- 文件分类和文件记录增加可见度字段，用于在系统内按角色过滤报价、PO 等敏感文件。

## 2. 编号策略

项目采用双编号：

| 编号 | 字段 | 是否必填 | 是否唯一 | 说明 |
|---|---|---|---|---|
| INQ号 | `intake_no` | 是 | 是 | 系统自动生成，项目创建时立即可用，用于前期工程支持 |
| WO号/内部设备号 | `equipment_no` | 否 | 填写后唯一 | 公司内部正式执行编号，可能后续补充 |

推荐 INQ号格式：

```text
INQ-YYYYMMDD-001
```

示例：

```text
INQ-20260527-001
```

WO号/内部设备号规则：

- 可为空。
- 填写后唯一。
- 大小写不敏感。
- 允许英文字母、数字、横杠、下划线。
- 推荐校验规则：`^[A-Za-z0-9_-]+$`。

## 3. 目录命名策略

新项目保存时创建项目目录。

目录编号优先级：

1. 如果已有 WO号/内部设备号，使用 `equipment_no`。
2. 如果暂时没有 WO号/内部设备号，使用 INQ号 `intake_no`。

推荐目录结构：

```text
D:\01_CustomerProject\
  客户公司名\
    编号_联系人_设备名称\
      01_输入资料\
      02_报价与订单\
        01_内部报价\
        02_对客报价\
        03_PO订单\
      03_方案与图纸\
      04_BOM与采购\
        01_BOM\
        02_采购商务\
      05_装配调试\
      06_验收发货\
      99_其他\
```

如果项目创建后才补充 WO号/内部设备号，系统不静默自动重命名已经创建的文件夹，而是在项目详情页提示：

```text
已补充 WO号/内部设备号，是否将项目文件夹从 INQ号重命名为正式 WO号？
```

用户确认后，系统只重命名项目叶子文件夹，并同步更新项目目录路径和文件索引路径；用户取消时保留原 INQ 文件夹名。

## 4. 核心关系

```text
系统配置 app_settings
币种 currencies
客户集团 customer_groups
  └─ 客户公司/法人主体 customers
      └─ 工厂/站点 customer_sites
          └─ 客户产品/生产线 project_groups
              ├─ 共享文件 project_group_files
              └─ 项目 projects
                  ├─ 项目文件 project_files
                  ├─ 报价记录 quotes
                  ├─ PO 记录 purchase_orders
                  ├─ 待办提醒 todos
                  └─ 项目事件 project_events
```

## 5. 字典和配置

### 5.1 app_settings 系统配置

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| key | TEXT | 是 | 配置键 |
| value | TEXT | 否 | 配置值 |
| updated_at | TEXT | 是 | 更新时间 |

初始配置：

| key | value |
|---|---|
| project_root_path | `D:\01_CustomerProject` |
| backup_target_path | 空 |
| default_currency | `CNY` |

### 5.2 currencies 币种

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | TEXT | 是 | 币种代码 |
| name | TEXT | 是 | 显示名称 |
| symbol | TEXT | 否 | 符号 |
| is_active | INTEGER | 是 | 是否启用 |

初始币种：

| code | name |
|---|---|
| CNY | 人民币 |
| USD | 美元 |

### 5.3 project_statuses 项目状态

保留 v0.1 状态，并增加一个状态：

| code | name |
|---|---|
| no_equipment_no | 待补WO号 |

当项目还没有 WO号/内部设备号时，可使用该状态，或继续使用 `询价录入` 并通过“WO号为空”筛选。

### 5.4 file_categories 文件分类

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | TEXT | 是 | 分类代码 |
| name | TEXT | 是 | 显示名称 |
| default_folder | TEXT | 是 | 默认归档目录 |
| default_visibility | TEXT | 是 | 默认可见度：`engineering`、`pm_only`、`admin_only` |
| sort_order | INTEGER | 是 | 排序 |
| is_active | INTEGER | 是 | 是否启用 |

当前默认可见度：

| 分类 | 可见度 |
|---|---|
| 询价需求 | `engineering` |
| 方案资料 | `engineering` |
| 内部报价 | `engineering` |
| 客户报价 | `pm_only` |
| PO 订单 | `pm_only` |
| 图纸模型 | `engineering` |
| 验收发货 | `engineering` |
| 沟通记录 | `engineering` |
| 其他 | `engineering` |

## 6. 主数据表调整

### 6.1 projects 项目

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| intake_no | TEXT | 是 | INQ号，唯一 |
| equipment_no | TEXT | 否 | WO号/内部设备号，填写后唯一 |
| source_type | TEXT | 是 | `new`、`historical_manual`、`historical_scan_pending` |
| project_group_id | TEXT | 否 | 客户产品/生产线 |
| customer_group_id | TEXT | 否 | 客户集团 |
| customer_id | TEXT | 是 | 客户公司 |
| site_id | TEXT | 否 | 工厂/站点 |
| department | TEXT | 否 | 部门/业务单元 |
| origin_role | TEXT | 否 | 项目来源角色 |
| po_customer_id | TEXT | 否 | PO/采购主体 |
| contact_id | TEXT | 否 | 客户联系人 |
| project_name | TEXT | 否 | 项目名称 |
| equipment_name | TEXT | 是 | 设备名称或项目主题 |
| status_code | TEXT | 是 | 当前项目状态 |
| currency_code | TEXT | 是 | 币种，默认 `CNY` |
| estimated_quote_amount | NUMERIC | 否 | 预计报价金额 |
| final_quote_amount | NUMERIC | 否 | 最终报价金额 |
| po_amount | NUMERIC | 否 | PO 金额 |
| inquiry_date | TEXT | 否 | 询价日期 |
| quote_date | TEXT | 否 | 报价日期 |
| po_date | TEXT | 否 | PO 日期 |
| expected_delivery_date | TEXT | 否 | 预计交期 |
| actual_ship_date | TEXT | 否 | 实际发货日期 |
| project_folder_path | TEXT | 否 | 系统项目文件夹 |
| original_source_path | TEXT | 否 | 原始资料路径，老项目常用 |
| has_quote | INTEGER | 是 | 是否有报价 |
| has_po | INTEGER | 是 | 是否有 PO |
| has_3d_model | INTEGER | 是 | 是否有 3D 模型 |
| is_historical | INTEGER | 是 | 是否历史项目 |
| is_data_complete | INTEGER | 是 | 资料是否完整 |
| is_archived | INTEGER | 是 | 是否归档 |
| notes | TEXT | 否 | 备注 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

关键约束：

- `intake_no` 必填且唯一。
- `equipment_no` 可以为空。
- `equipment_no` 填写后唯一，大小写不敏感。
- `equipment_name` 第一阶段建议必填，用于目录命名。

### 6.2 quotes 报价记录

字段 `currency` 改为 `currency_code`，关联 `currencies.code`。

### 6.3 purchase_orders PO 记录

字段 `currency` 改为 `currency_code`，关联 `currencies.code`。

### 6.4 project_files 项目文件

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| project_id | TEXT | 是 | 所属项目 |
| original_name | TEXT | 是 | 原文件名 |
| current_name | TEXT | 是 | 当前文件名 |
| extension | TEXT | 否 | 扩展名 |
| category_code | TEXT | 是 | 文件分类 |
| visibility_code | TEXT | 是 | 文件可见度，默认跟随分类 |
| file_path | TEXT | 是 | 文件路径 |
| original_source_path | TEXT | 否 | 原始来源路径 |
| size_bytes | INTEGER | 否 | 文件大小 |
| modified_at | TEXT | 否 | 文件修改时间 |
| is_3d_model | INTEGER | 是 | 是否 3D/图纸模型 |
| text_extracted | INTEGER | 是 | 是否已提取文本 |
| extracted_text | TEXT | 否 | 提取文本 |
| content_hash | TEXT | 否 | 内容哈希 |
| import_method | TEXT | 是 | 导入方式 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

### 6.5 project_group_files 共享文件

与 `project_files` 类似，但归属于 `project_group_id`。同样使用 `visibility_code` 控制系统内可见度。

当前可见度只保护系统页面和 API 返回结果；直接浏览 NAS/共享目录必须依赖 NAS / Windows ACL。

## 7. 当前确认配置

| 配置 | 当前值 |
|---|---|
| 项目文件根目录 | `D:\01_CustomerProject` |
| 默认币种 | `CNY` |
| 支持币种 | `CNY`、`USD` |
| 备份目录 | 待定 |
| 第一阶段形态 | 本地 Web 原型 |
| 后续形态 | 桌面软件 |

## 8. 仍需确认

1. INQ号格式是否接受 `INQ-YYYYMMDD-001`。
2. 备份目录最终放移动硬盘、NAS 还是网盘同步目录。
3. 是否需要支持更多币种，例如 `EUR`、`JPY`。
