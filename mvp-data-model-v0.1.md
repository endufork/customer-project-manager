# 客户项目资料管理系统 MVP 数据模型 v0.1

## 1. 设计目标

本数据模型用于第一阶段 MVP，重点支持：

- 新项目标准录入
- 老项目按需补录
- 项目设备号唯一管控
- 文件复制、分类、索引
- 报价和 PO 多记录管理
- 待办提醒
- Excel 导出
- 数据库和索引备份

数据库建议使用 SQLite。日期时间统一使用 ISO 8601 文本格式，例如 `2026-05-27` 或 `2026-05-27T15:30:00+08:00`。

## 2. 核心关系

```text
客户公司 customers
  └─ 客户联系人 contacts
       └─ 项目 projects
            ├─ 项目文件 project_files
            ├─ 报价记录 quotes
            ├─ PO 记录 purchase_orders
            ├─ 待办提醒 todos
            └─ 项目事件 project_events
```

项目以 `项目设备号 equipment_no` 作为业务唯一编号。

系统内部仍建议使用 `id` 作为主键，避免未来项目设备号格式变化、录入修正或系统对接时影响关联关系。

## 3. 字典表

### 3.1 project_statuses 项目状态

用于维护项目生命周期状态。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | TEXT | 是 | 状态代码，例如 `inquiry` |
| name | TEXT | 是 | 显示名称，例如 `询价录入` |
| sort_order | INTEGER | 是 | 排序 |
| is_active | INTEGER | 是 | 是否启用，0/1 |

初始状态建议：

| code | name |
|---|---|
| inquiry | 询价录入 |
| clarification | 需求澄清 |
| solution_design | 方案设计 |
| cost_review | 内部评估/成本核算 |
| internal_quote | 内部工程师报价 |
| quoted | 已向客户报价 |
| waiting_feedback | 等待客户反馈 |
| po_received | 客户已下 PO |
| purchasing | 备料/采购 |
| manufacturing | 装配/制作 |
| acceptance | 验收/调试 |
| shipped | 已发货 |
| completed | 项目完成 |
| paused | 暂停 |
| lost_closed | 丢单/关闭 |
| historical_entry | 历史补录 |

### 3.2 file_categories 文件分类

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | TEXT | 是 | 分类代码 |
| name | TEXT | 是 | 分类名称 |
| default_folder | TEXT | 是 | 默认目录名 |
| sort_order | INTEGER | 是 | 排序 |
| is_active | INTEGER | 是 | 是否启用 |

初始分类建议：

| code | name | default_folder |
|---|---|---|
| inquiry | 询价需求 | 01_询价需求 |
| solution | 方案资料 | 02_方案资料 |
| internal_quote | 内部报价 | 03_内部报价 |
| customer_quote | 客户报价 | 04_客户报价 |
| po | PO 订单 | 05_PO订单 |
| drawing_model | 图纸模型 | 06_图纸模型 |
| acceptance_delivery | 验收发货 | 07_验收发货 |
| communication | 沟通记录 | 08_沟通记录 |
| other | 其他 | 99_其他 |

### 3.3 todo_types 待办类型

| code | name |
|---|---|
| quote_deadline | 报价截止 |
| customer_followup | 客户跟进 |
| internal_review | 内部评估 |
| delivery | 交期提醒 |
| acceptance | 验收提醒 |
| shipment | 发货提醒 |
| historical_cleanup | 历史资料补全 |
| other | 其他 |

## 4. 主数据表

### 4.1 customers 客户公司

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键，建议 UUID |
| name | TEXT | 是 | 客户公司全称，唯一 |
| short_name | TEXT | 否 | 客户简称 |
| country_region | TEXT | 否 | 国家/地区 |
| industry | TEXT | 否 | 行业 |
| notes | TEXT | 否 | 备注 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

约束：

- `name` 不允许为空。
- `name` 建议唯一，但后续可通过“别名表”解决客户多名称问题。

### 4.2 contacts 客户联系人

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| customer_id | TEXT | 是 | 所属客户 |
| name | TEXT | 是 | 联系人姓名 |
| role | TEXT | 否 | 工程师、项目经理、采购等 |
| phone | TEXT | 否 | 电话 |
| email | TEXT | 否 | 邮箱 |
| wechat | TEXT | 否 | 微信 |
| is_primary | INTEGER | 是 | 是否主要联系人，0/1 |
| notes | TEXT | 否 | 备注 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

说明：

- 暂不强制联系人姓名唯一，因为不同客户或同客户内都可能出现重名。
- 可在界面中用“客户 + 姓名 + 邮箱/微信”辅助识别。

### 4.3 projects 项目

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| equipment_no | TEXT | 是 | 项目设备号，业务唯一 |
| source_type | TEXT | 是 | `new`、`historical_manual`、`historical_scan_pending` |
| customer_id | TEXT | 是 | 客户公司 |
| contact_id | TEXT | 否 | 客户联系人 |
| project_name | TEXT | 否 | 项目名称 |
| equipment_name | TEXT | 否 | 设备名称 |
| status_code | TEXT | 是 | 当前项目状态 |
| currency | TEXT | 是 | 币种，例如 `CNY`、`USD`、`EUR` |
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

- `equipment_no` 唯一，大小写不敏感。
- 新项目 `source_type = new`。
- 老项目手动补录 `source_type = historical_manual`。
- 批量扫描但未确认的项目 `source_type = historical_scan_pending`，放到第二阶段。

### 4.4 project_files 项目文件

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| project_id | TEXT | 是 | 所属项目 |
| original_name | TEXT | 是 | 原始文件名 |
| current_name | TEXT | 是 | 当前文件名，第一阶段通常等于原始文件名 |
| extension | TEXT | 否 | 文件扩展名，小写 |
| category_code | TEXT | 是 | 文件分类 |
| file_path | TEXT | 是 | 系统文件路径或绑定文件路径 |
| original_source_path | TEXT | 否 | 原始来源路径 |
| size_bytes | INTEGER | 否 | 文件大小 |
| modified_at | TEXT | 否 | 文件修改时间 |
| is_3d_model | INTEGER | 是 | 是否 3D 模型 |
| text_extracted | INTEGER | 是 | 是否已提取文本 |
| extracted_text | TEXT | 否 | 提取文本 |
| content_hash | TEXT | 否 | 文件哈希，用于去重 |
| import_method | TEXT | 是 | `new_project_copy`、`historical_link`、`historical_copy`、`scan_pending` |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

说明：

- 新项目文件默认复制到系统项目目录，`import_method = new_project_copy`。
- 老项目可以只绑定路径，`import_method = historical_link`。
- 第一阶段不要求实时监控文件变化。

### 4.5 quotes 报价记录

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| project_id | TEXT | 是 | 所属项目 |
| version_label | TEXT | 否 | 报价版本，例如 `V1`、`V2` |
| quote_date | TEXT | 否 | 报价日期 |
| amount | NUMERIC | 否 | 报价金额 |
| currency | TEXT | 是 | 币种 |
| file_id | TEXT | 否 | 关联报价文件 |
| is_final | INTEGER | 是 | 是否最终版本 |
| notes | TEXT | 否 | 备注 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

说明：

- 一个项目可以有多个报价。
- 标记最终报价后，项目表中的 `final_quote_amount` 可同步更新。

### 4.6 purchase_orders PO 记录

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| project_id | TEXT | 是 | 所属项目 |
| po_no | TEXT | 否 | PO 编号 |
| po_date | TEXT | 否 | PO 日期 |
| amount | NUMERIC | 否 | PO 金额 |
| currency | TEXT | 是 | 币种 |
| file_id | TEXT | 否 | 关联 PO 文件 |
| is_partial | INTEGER | 是 | 是否分批 PO |
| notes | TEXT | 否 | 备注 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

说明：

- 一个项目可以有多个 PO。
- 项目表中的 `po_amount` 可以统计所有 PO 金额，也可以由用户手动确认，第一阶段建议界面显示“PO 合计”。

### 4.7 todos 待办提醒

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| project_id | TEXT | 否 | 关联项目 |
| type_code | TEXT | 是 | 待办类型 |
| title | TEXT | 是 | 标题 |
| due_date | TEXT | 是 | 到期日期 |
| status | TEXT | 是 | `open`、`completed`、`cancelled` |
| completed_at | TEXT | 否 | 完成时间 |
| notes | TEXT | 否 | 备注 |
| created_at | TEXT | 是 | 创建时间 |
| updated_at | TEXT | 是 | 更新时间 |

说明：

- 待办可关联项目，也可保留少量独立待办。
- 新项目报价后可自动建议创建客户跟进待办。

### 4.8 project_events 项目事件

用于项目详情页时间线。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| project_id | TEXT | 是 | 所属项目 |
| event_type | TEXT | 是 | 事件类型 |
| title | TEXT | 是 | 事件标题 |
| detail | TEXT | 否 | 事件详情 |
| created_at | TEXT | 是 | 创建时间 |

事件类型示例：

- `project_created`
- `status_changed`
- `file_imported`
- `quote_added`
- `po_added`
- `todo_added`
- `backup_created`

### 4.9 backup_records 备份记录

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | TEXT | 是 | 系统主键 |
| backup_type | TEXT | 是 | `database`、`index`、`config`、`full` |
| backup_path | TEXT | 是 | 备份路径 |
| status | TEXT | 是 | `success`、`failed` |
| message | TEXT | 否 | 结果说明 |
| created_at | TEXT | 是 | 创建时间 |

## 5. 推荐索引

项目常用索引：

- `projects.equipment_no`
- `projects.customer_id`
- `projects.contact_id`
- `projects.status_code`
- `projects.source_type`
- `projects.inquiry_date`
- `projects.expected_delivery_date`
- `projects.has_po`
- `projects.has_3d_model`

文件常用索引：

- `project_files.project_id`
- `project_files.category_code`
- `project_files.extension`
- `project_files.content_hash`
- `project_files.import_method`

待办常用索引：

- `todos.project_id`
- `todos.status`
- `todos.due_date`
- `todos.type_code`

## 6. 第一阶段不做但预留

第一阶段暂不开发，但数据模型已留出空间：

- 多用户权限：后续可增加 `users`、`roles`、`audit_logs`。
- 客户别名：后续可增加 `customer_aliases`。
- 邮件导入：后续可增加 `external_sources`、`source_messages`。
- 微信导入：后续可作为外部来源之一。
- 历史批量扫描：项目来源中已预留 `historical_scan_pending`。
- 文件去重：文件表已预留 `content_hash`。

## 7. 当前仍需确认

1. 项目设备号是否大小写敏感。当前建议大小写不敏感。
2. 项目设备号是否允许横杠、下划线或空格。
3. 默认币种是否为 `CNY`。
4. 新项目创建时，客户公司是否必须已知。
5. 项目文件根目录放在哪个磁盘或路径下。
6. 备份目录放在哪个磁盘或路径下。

