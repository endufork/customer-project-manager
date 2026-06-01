# 后端模块结构

当前后端采用“模块化单体”：系统仍然是一个本地 Web 应用，但业务代码按职责拆分，方便后续逐步升级到桌面版、备份模块、全文搜索或更多自动化能力。

## 入口层

```text
app.py
customer_m/server.py
```

`app.py` 是启动入口。`customer_m/server.py` 是 Web API 网关，负责 HTTP 路由、JSON 请求/响应、本地静态页面服务。

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

项目基础规则模块。负责内部设备号校验、项目性质规范化。

```text
customer_m/modules/lifecycle.py
```

项目生命周期辅助模块。当前负责临时项目号生成和项目事件记录，后续可扩展状态流转、待办、提醒、交期逻辑。

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

这是第一阶段重构保留的兼容出口。旧代码仍然可以从 `customer_m.services` 调用业务函数，新代码优先直接从 `customer_m.modules.*` 导入。

## 后续拆分方向

下一阶段可以继续把 `server.py` 中较重的 SQL 查询和项目创建/更新流程下沉到业务模块，让 Web API 网关只负责路由和请求响应。
