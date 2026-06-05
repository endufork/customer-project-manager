# 后端模块结构

当前后端采用“模块化单体”：系统仍然是一个本地 Web 应用，但业务代码按职责拆分，方便后续逐步升级到桌面版、备份模块、全文搜索或更多自动化能力。

## 入口层

```text
app.py
customer_m/fastapi_app.py
customer_m/api/
```

`app.py` 是本地启动入口。`customer_m/fastapi_app.py` 是 FastAPI 应用入口，负责注册 API 路由、静态页面和启动初始化。`customer_m/api/` 放声明式 HTTP 路由和请求体验证；它不直接处理客户、项目、目录和文件业务，只负责调用业务模块。

## 数据层

```text
customer_m/database.py
customer_m/config.py
customer_m/utils.py
```

`database.py` 管理 SQLite 连接、初始化和迁移。`config.py` 保存目录名、项目性质、文件分类、模型文件扩展名等配置。`utils.py` 保存通用小工具。

## 业务模块

```text
customer_m/modules/customers.py
```

客户与联系人管理模块。负责客户集团、客户公司/法人主体、工厂/站点、联系人创建和复用。

```text
customer_m/modules/projects.py
```

项目模块门面。对 API 层和旧兼容层暴露统一入口，内部转发到项目规则、查询和写入流程模块。

```text
customer_m/modules/project_rules.py
```

项目基础规则模块。负责 WO号/内部设备号校验、项目性质规范化。

```text
customer_m/modules/project_queries.py
```

项目查询模块。负责项目列表、详情、项目文件夹路径、共享资料路径等只读数据。

```text
customer_m/modules/project_commands.py
```

项目写入流程模块。负责项目创建、修改、删除、共享资料扫描等会改变数据库或文件系统状态的流程编排。

```text
customer_m/modules/lookups.py
```

基础下拉数据模块。负责启动页需要的设置、状态、币种、客户、工厂、联系人、项目性质等表单选项。

```text
customer_m/modules/lifecycle.py
```

项目生命周期辅助模块。当前负责 INQ号生成、项目事件记录、默认待办创建，后续可扩展状态流转、提醒、交期逻辑。

```text
customer_m/modules/folders.py
```

自动化文件与目录管家。负责客户/工厂/产品/项目目录生成、标准子目录创建、目录迁移、资料删除保护。

```text
customer_m/modules/file_types.py
```

文件类型判断模块。根据文件名和扩展名判断询价、报价、PO、方案、模型、交付资料等分类。

```text
customer_m/modules/parsers.py
```

文档内容解析引擎。负责 TXT、CSV、Word、Excel、PDF 的文本提取。

```text
customer_m/modules/file_import.py
```

导入模块。负责从散乱文件/文件夹复制到项目标准目录，并写入文件索引。

```text
customer_m/modules/scanner.py
```

状态扫描与差异同步模块。负责扫描项目目录和客户产品共享资料目录，发现新文件，计算 hash，更新文件索引和项目标记。

## 兼容层

```text
customer_m/services.py
```

这是第一阶段重构保留的兼容出口。新代码优先直接从 `customer_m.modules.*` 导入。

## 后续拆分方向

下一阶段可以继续把设置管理、备份、导出、搜索做成独立模块，并把项目生命周期状态流转从 `projects.py` 继续拆到 `lifecycle.py`。
