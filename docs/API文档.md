# 电商智能定价平台 API 文档（可读版）

更新日期：2026-04-23

本文档基于当前仓库代码整理，主要依据以下源码入口：

- Java 对外 API：`backend-java/src/main/java/com/example/pricing/controller/*.java`
- Python 内部 API：`backend-python/app/api/*.py`
- 前端调用封装：`frontend/src/api/*.ts`
- 共享数据结构：`backend-java/src/main/java/com/example/pricing/dto/*.java`、`backend-java/src/main/java/com/example/pricing/vo/*.java`、`backend-python/app/schemas/*.py`

## 1. 总览

### 1.1 运行边界

- 浏览器只访问 Java 对外接口：`/api/**`
- Python HTTP 接口是内部接口，默认前缀为 `/internal/**`
- Java 与 Python 的内部协作同时使用 RabbitMQ 和内部 HTTP
- 实时任务流使用 Java SSE：`GET /api/pricing/tasks/{taskId}/events`

### 1.2 鉴权规则

- 无需 Bearer Token：
  - `POST /api/user/login`
  - `POST /api/user/refresh`
  - `GET /api/health`
  - `GET /api/health/live`
  - `GET /api/health/ready`
  - `GET /api/health/metrics`
- 其余 Java `/api/**` 接口都要求请求头：`Authorization: Bearer <access_token>`
- `POST /api/user/refresh` 依赖登录后写入的 Refresh Token Cookie
- Python 内部接口要求请求头：`X-Internal-Token: <token>`
- Python 在 `dev` 环境下允许“内部令牌为空 + 显式开启 bypass”时跳过校验；`prod` 环境必须校验

### 1.3 Java 统一响应结构

除文件下载和 SSE 外，Java 接口默认返回：

```json
{
  "code": 200,
  "message": "Success",
  "data": {},
  "traceId": "..."
}
```

字段说明：

- `code`：业务码，成功固定为 `200`
- `message`：成功通常为 `Success`，失败时为错误消息
- `data`：业务数据，可能为对象、数组、分页对象或 `null`
- `traceId`：链路追踪 ID；拦截器直接返回的 401 响应可能不带该字段

常见错误码：

- `400`：参数不合法
- `401`：未登录、令牌失效、会话过期
- `403`：权限不足
- `429`：登录尝试次数过多
- `500`：服务端错误

### 1.4 常见公共结构

#### 1.4.1 分页对象 `Page<T>`

多个列表接口返回 MyBatis-Plus 分页对象，核心字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `current` | number | 当前页码 |
| `size` | number | 每页条数 |
| `total` | number | 总记录数 |
| `records` | `T[]` | 当前页数据 |
| `pages` | number | 总页数 |

#### 1.4.2 策略目标 `strategyGoal`

前端当前使用的策略目标枚举：

| 值 | 含义 |
| --- | --- |
| `MAX_PROFIT` | 利润优先 |
| `CLEARANCE` | 清仓促销 |
| `MARKET_SHARE` | 市场份额优先 |

#### 1.4.3 定价任务状态 `taskStatus`

| 值 | 含义 |
| --- | --- |
| `PENDING` | 已创建，待派发 |
| `QUEUED` | 已入队，待执行 |
| `RUNNING` | 执行中 |
| `RETRYING` | 重试中 |
| `MANUAL_REVIEW` | 已产出结果，但需要人工审核 |
| `COMPLETED` | 已完成 |
| `FAILED` | 执行失败 |
| `CANCELLED` | 已取消 |

#### 1.4.4 批量任务状态 `batchStatus`

当前批次聚合状态来自 `PricingBatchServiceImpl`，实际可能值为：

| 值 | 含义 |
| --- | --- |
| `RUNNING` | 批次内仍有任务执行中 |
| `COMPLETED` | 全部完成 |
| `MANUAL_REVIEW` | 全部结束，且至少一项需要人工审核 |
| `FAILED` | 全部失败 |
| `CANCELLED` | 全部取消 |
| `PARTIAL_FAILED` | 部分失败或部分取消 |

批次明细里的 `displayStatus` 还可能出现：

| 值 | 含义 |
| --- | --- |
| `CREATE_FAILED` | 该商品创建子任务时失败 |

#### 1.4.5 定价约束 `constraints`

对外接口里的 `constraints` 是字符串。前端当前会把约束表单序列化为 JSON 字符串，例如：

```json
{"min_profit_rate":0.15,"min_price":79.9,"max_price":129,"max_discount_rate":0.2,"force_manual_review":true}
```

可能出现的键：

- `min_profit_rate`
- `min_price`
- `max_price`
- `max_discount_rate`
- `force_manual_review`

### 1.5 特殊返回类型

- 文件下载：
  - `GET /api/products/template`
  - `GET /api/decision/export/{taskId}`
- SSE：
  - `GET /api/pricing/tasks/{taskId}/events`

## 2. Java 对外 API

### 2.1 用户与会话

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/user/login` | `POST` | 否 | JSON：`LoginBody` | `Result<LoginResponse>` | 登录成功后同时写入 Refresh Token Cookie |
| `/api/user/refresh` | `POST` | 否 | 无请求体 | `Result<LoginResponse>` | 用 Refresh Cookie 换新 access token |
| `/api/user/logout` | `POST` | Bearer | 无请求体 | `Result<null>` | 撤销当前会话并清除 Refresh Cookie |
| `/api/user/list` | `GET` | Bearer + Admin | Query：`page`、`size` | `Result<Page<UserListVO>>` | 用户列表 |
| `/api/user/add` | `POST` | Bearer + Admin | JSON：`UserCreateBody` | `Result<null>` | 新增用户 |
| `/api/user/{id}` | `PUT` | Bearer + Admin | Path：`id`，JSON：`UserUpdateBody` | `Result<null>` | 更新用户 |
| `/api/user/{id}` | `DELETE` | Bearer + Admin | Path：`id` | `Result<null>` | 删除用户，管理员不可删除 |
| `/api/user/batch-delete` | `DELETE` | Bearer + Admin | Query：`ids` | `Result<null>` | 批量删除用户，管理员不可删除 |

#### 2.1.1 对象定义

##### `LoginBody`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名；后端也允许传账号名 |
| `password` | string | 是 | 明文密码 |

##### `LoginResponse`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `token` | string | Access Token |
| `username` | string | 当前用户名 |
| `role` | string | `ADMIN` 或 `USER` |
| `isAdmin` | boolean | 是否管理员 |

##### `UserListVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 用户 ID |
| `username` | string | 用户名 |
| `email` | string | 邮箱 |
| `status` | number | 状态，代码中常见 `1` 启用、`0` 禁用 |
| `role` | string | 角色 |
| `createdAt` | string(datetime) | 创建时间 |
| `updatedAt` | string(datetime) | 更新时间 |

##### `UserCreateBody`

`/api/user/add` 当前直接接收 `SysUser` 实体，请求体可用字段如下：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名，后端会同步写入 `account` |
| `password` | string | 是 | 明文密码，后端按 BCrypt 加密 |
| `email` | string | 否 | 邮箱 |
| `status` | number | 否 | 默认 `1` |
| `role` | string | 否 | 默认 `USER`，只接受 `ADMIN`/`USER` |

##### `UserUpdateBody`

`/api/user/{id}` 当前也接收 `SysUser` 实体，实际参与更新的字段如下：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 否 | 改名时会同步更新 `account` |
| `password` | string | 否 | 传空串视为不改 |
| `email` | string | 否 | 邮箱 |
| `status` | number | 否 | 状态变更会使旧 token 失效 |
| `role` | string | 否 | 角色变更会使旧 token 失效 |

#### 2.1.2 额外说明

- 登录失败可能返回：
  - `401/500` 风格业务错误：用户名或密码错误
  - `429`：登录被限流
- `logout`、用户管理、店铺/商品/任务类接口都走 Bearer Token 鉴权
- `/api/user/batch-delete` 的 `ids` 前端当前使用逗号拼接形式：`ids=1,2,3`

### 2.2 用户 LLM 配置

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/user/llm-config` | `GET` | Bearer | 无 | `Result<UserLlmConfigVO \| null>` | 获取当前用户模型配置 |
| `/api/user/llm-config` | `PUT` | Bearer | JSON：`UserLlmConfigDTO` | `Result<null>` | 保存或更新配置 |
| `/api/user/llm-config` | `DELETE` | Bearer | 无 | `Result<null>` | 删除当前用户配置 |
| `/api/user/llm-config/verify` | `POST` | Bearer | JSON：`UserLlmConfigDTO` | `Result<string>` | 校验模型服务连通性 |

#### 2.2.1 对象定义

##### `UserLlmConfigDTO`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `apiKey` | string | 首次保存必填；更新时可选 | 模型服务密钥 |
| `baseUrl` | string | 是 | 模型服务基础地址 |
| `model` | string | 是 | 模型名 |

##### `UserLlmConfigVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `baseUrl` | string | 当前基础地址 |
| `model` | string | 当前模型名 |
| `hasApiKey` | boolean | 是否已配置密钥 |
| `apiKeyPreview` | string | 脱敏展示值 |
| `apiKey` | string | 当前源码会把解密后的完整密钥返回给前端 |

#### 2.2.2 额外说明

- `/verify` 会向 `baseUrl/chat/completions` 发起一次轻量请求
- `/verify` 要求 `apiKey`、`baseUrl`、`model` 都非空
- 首次 `PUT` 保存时如果 `apiKey` 为空会报错

### 2.3 店铺

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/shops` | `GET` | Bearer | 无 | `Result<Shop[]>` | 查询当前用户的店铺列表 |
| `/api/shops` | `POST` | Bearer | JSON：`ShopCreateDTO` | `Result<Shop>` | 新增店铺 |
| `/api/shops/{id}` | `PUT` | Bearer | Path：`id`，JSON：`ShopUpdateDTO` | `Result<Shop>` | 更新店铺 |
| `/api/shops/{id}` | `DELETE` | Bearer | Path：`id` | `Result<null>` | 删除店铺 |

#### 2.3.1 对象定义

##### `ShopCreateDTO` / `ShopUpdateDTO`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `shopName` | string | 是 | 店铺名称 |
| `platform` | string | 是 | 平台标识或平台名称 |
| `sellerNick` | string | 否 | 卖家昵称 |

##### `Shop`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 店铺 ID |
| `userId` | number | 所属用户 ID |
| `shopName` | string | 店铺名称 |
| `platform` | string | 平台 |
| `sellerNick` | string | 卖家昵称 |
| `createdAt` | string(datetime) | 创建时间 |
| `updatedAt` | string(datetime) | 更新时间 |

### 2.4 商品

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/products/import` | `POST` | Bearer | `multipart/form-data`：`file`、`dataType?`、`platform?`、`shopId` | `Result<ImportResultVO>` | 导入 Excel |
| `/api/products/template` | `GET` | Bearer | Query：`dataType?` | Excel 二进制文件 | 下载导入模板 |
| `/api/products/add` | `POST` | Bearer | JSON：`ProductManualDTO` | `Result<null>` | 手工新增商品 |
| `/api/products/list` | `GET` | Bearer | Query：`page`、`size`、`keyword?`、`dataSource?`、`platform?`、`status?`、`shopId?` | `Result<Page<ProductListVO>>` | 商品分页列表 |
| `/api/products/batch-delete` | `DELETE` | Bearer | Query：`ids` | `Result<null>` | 批量删除商品 |
| `/api/products/{id}/trend` | `GET` | Bearer | Path：`id`，Query：`days=30` | `Result<ProductTrendVO>` | 商品趋势与增长概览 |
| `/api/products/{id}/daily-metrics` | `GET` | Bearer | Path：`id`，Query：`page=1`、`size=10` | `Result<ProductDailyMetricPageVO>` | 商品经营日报 |
| `/api/products/{id}/skus` | `GET` | Bearer | Path：`id` | `Result<ProductSkuVO[]>` | SKU 明细 |
| `/api/products/{id}/traffic-promo` | `GET` | Bearer | Path：`id`，Query：`limit=90` | `Result<TrafficPromoDailyVO[]>` | 流量推广日报 |

#### 2.4.1 导入接口补充说明

`/api/products/import` 支持的 `dataType`：

| 值 | 含义 |
| --- | --- |
| `AUTO` | 自动识别 |
| `PRODUCT_BASE` | 商品基础信息 |
| `PRODUCT_SKU` | 商品 SKU |
| `PRODUCT_DAILY_METRIC` | 商品经营日报 |
| `TRAFFIC_PROMO_DAILY` | 流量推广日报 |

导入规则：

- 仅支持 `.xls` / `.xlsx`
- 文件大小不超过 `10MB`
- `shopId` 必填
- `platform` 可选；当前对外接口已经优先使用 `shopId`

`/api/products/template` 的 `dataType` 为空或为 `AUTO` 时，默认返回 `PRODUCT_BASE` 模板。

#### 2.4.2 对象定义

##### `ProductManualDTO`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `externalProductId` | string | 否 |  | 外部商品 ID |
| `productName` | string | 是 |  | 商品名 |
| `categoryName` | string | 否 |  | 类目名 |
| `costPrice` | number | 是 |  | 成本价 |
| `salePrice` | number | 是 |  | 售价 |
| `stock` | number | 否 |  | 库存 |
| `monthlySales` | number | 否 | `0` | 月销量 |
| `conversionRate` | number | 否 | `0` | 转化率 |
| `status` | string | 否 | `出售中` | 当前服务只接受 `出售中` 或 `下架` |

##### `ImportResultVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dataType` | string | 导入类型代码 |
| `dataTypeLabel` | string | 导入类型中文名 |
| `targetTable` | string | 目标表名 |
| `fileName` | string | 原始文件名 |
| `rowCount` | number | 总行数 |
| `successCount` | number | 成功行数 |
| `failCount` | number | 失败行数 |
| `uploadStatus` | string | `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED` |
| `startDate` | string(date) | 导入数据开始日期 |
| `endDate` | string(date) | 导入数据结束日期 |
| `autoDetected` | boolean | 是否自动识别类型 |
| `summary` | string | 摘要说明 |
| `errors` | string[] | 错误列表，最多保留前 10 条 |

##### `ProductListVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 商品 ID |
| `shopId` | number | 店铺 ID |
| `platform` | string | 平台 |
| `externalProductId` | string | 外部商品 ID |
| `productName` | string | 商品名 |
| `shortTitle` | string | 短标题 |
| `subTitle` | string | 副标题 |
| `categoryName` | string | 类目 |
| `primaryCategoryName` | string | 一级类目 |
| `secondaryCategoryName` | string | 二级类目 |
| `costPrice` | number | 成本价 |
| `salePrice` | number | 售价 |
| `stock` | number | 库存 |
| `status` | string | 商品状态 |
| `monthlySales` | number | 月销量 |
| `conversionRate` | number | 转化率 |
| `updatedAt` | string(datetime) | 更新时间 |

##### `ProductTrendVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dates` | string[] | 日期序列 |
| `visitors` | number[] | 访客数序列 |
| `sales` | number[] | 销量序列 |
| `conversionRates` | number[] | 转化率序列 |
| `avgOrderValues` | number[] | 客单价序列 |
| `currentDailySales` | number | 当前日销量 |
| `currentMonthlySales` | number | 当前月销量 |
| `currentDailyProfit` | number | 当前日利润 |
| `currentMonthlyProfit` | number | 当前月利润 |
| `dailySalesGrowth` | number | 日销量增长值 |
| `dailySalesGrowthRate` | number | 日销量增长率 |
| `monthlySalesGrowth` | number | 月销量增长值 |
| `monthlySalesGrowthRate` | number | 月销量增长率 |
| `dailyProfitGrowth` | number | 日利润增长值 |
| `dailyProfitGrowthRate` | number | 日利润增长率 |
| `monthlyProfitGrowth` | number | 月利润增长值 |
| `monthlyProfitGrowthRate` | number | 月利润增长率 |

##### `ProductDailyMetricPageVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `page` | number | 当前页 |
| `size` | number | 每页条数 |
| `total` | number | 总条数 |
| `records` | `ProductDailyMetricVO[]` | 数据明细 |
| `summary` | object | 汇总信息 |

`summary` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `days` | number | 覆盖天数 |
| `totalVisitors` | number | 总访客数 |
| `totalTurnover` | number | 总成交额 |
| `avgConversionRate` | number | 平均转化率 |

##### `ProductDailyMetricVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 记录 ID |
| `statDate` | string(date) | 统计日期 |
| `visitorCount` | number | 访客数 |
| `addCartCount` | number | 加购人数 |
| `payBuyerCount` | number | 支付买家数 |
| `salesCount` | number | 支付件数 |
| `turnover` | number | 支付金额 |
| `refundAmount` | number | 退款金额 |
| `conversionRate` | number | 转化率 |
| `createdAt` | string(datetime) | 创建时间 |

##### `ProductSkuVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | SKU 记录 ID |
| `externalSkuId` | string | 外部 SKU ID |
| `skuName` | string | SKU 名称 |
| `skuAttr` | string | SKU 属性 |
| `salePrice` | number | 销售价 |
| `costPrice` | number | 成本价 |
| `stock` | number | 库存 |
| `updatedAt` | string(datetime) | 更新时间 |

##### `TrafficPromoDailyVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 记录 ID |
| `statDate` | string(date) | 统计日期 |
| `trafficSource` | string | 流量来源 |
| `impressionCount` | number | 展现量 |
| `clickCount` | number | 点击量 |
| `visitorCount` | number | 访客数 |
| `costAmount` | number | 花费 |
| `payAmount` | number | 支付金额 |
| `roi` | number | ROI |
| `createdAt` | string(datetime) | 创建时间 |

### 2.5 决策任务（旧版兼容接口）

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/decision/start` | `POST` | Bearer | JSON：`DecisionStartBody` | `Result<number>` | 创建决策任务并返回 `taskId` |
| `/api/decision/result/{taskId}` | `GET` | Bearer | Path：`taskId` | `Result<DecisionComparisonVO[]>` | 查询结果 |
| `/api/decision/logs/{taskId}` | `GET` | Bearer | Path：`taskId` | `Result<DecisionLogVO[]>` | 查询日志 |
| `/api/decision/tasks` | `GET` | Bearer | Query：`page=1`、`size=10`、`status?`、`startTime?`、`endTime?`、`sortOrder=desc` | `Result<Page<DecisionTaskItemVO>>` | 历史任务列表 |
| `/api/decision/tasks/stats` | `GET` | Bearer | Query：`startTime?`、`endTime?` | `Result<DecisionTaskStats>` | 任务统计 |
| `/api/decision/comparison/{taskId}` | `GET` | Bearer | Path：`taskId` | `Result<DecisionComparisonVO[]>` | 查询价格对比 |
| `/api/decision/apply/{resultId}` | `POST` | Bearer | Path：`resultId` | `Result<null>` | 应用价格建议到商品当前售价 |
| `/api/decision/export/{taskId}` | `GET` | Bearer | Path：`taskId` | Excel 二进制文件 | 导出报告 |

#### 2.5.1 对象定义

##### `DecisionStartBody`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `productIds` | number[] | 是 | 商品 ID 列表 |
| `strategyGoal` | string | 是 | 策略目标 |
| `constraints` | string | 否 | 约束字符串 |

##### `DecisionTaskStats`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `total` | number | 总任务数 |
| `completed` | number | 已完成数；代码中把 `MANUAL_REVIEW` 也计入 completed |
| `running` | number | 运行中；代码中把 `QUEUED` / `RUNNING` / `RETRYING` 计入 running |
| `failed` | number | 失败数；代码中把 `FAILED` / `CANCELLED` 计入 failed |

##### `DecisionTaskItemVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 任务 ID |
| `taskCode` | string | 任务编码 |
| `productId` | number | 商品 ID |
| `productTitle` | string | 商品标题 |
| `currentPrice` | number | 当前价格 |
| `suggestedMinPrice` | number | 建议最低价 |
| `suggestedMaxPrice` | number | 建议最高价 |
| `finalPrice` | number | 最终建议价 |
| `taskStatus` | string | 任务状态 |
| `executeStrategy` | string | 执行策略 |
| `createdAt` | string(datetime) | 创建时间 |

##### `DecisionComparisonVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `resultId` | number | 结果 ID |
| `productId` | number | 商品 ID |
| `productTitle` | string | 商品标题 |
| `originalPrice` | number | 原价 |
| `suggestedPrice` | number | 建议价 |
| `profitChange` | number | 利润变化值 |
| `expectedSales` | number | 预期销量 |
| `expectedProfit` | number | 预期利润 |
| `passStatus` | string | 是否通过 |
| `executeStrategy` | string | 执行策略 |
| `resultSummary` | string | 结果摘要 |
| `appliedStatus` | string | 应用状态 |

##### `DecisionLogVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 日志 ID |
| `taskId` | number | 任务 ID |
| `roleName` | string | 角色名 |
| `speakOrder` | number | 原始顺序 |
| `thoughtContent` | string | 原始思考内容 |
| `agentCode` | string | 智能体代码 |
| `agentName` | string | 智能体名称 |
| `runAttempt` | number | 第几次尝试 |
| `runOrder` | number | 运行顺序 |
| `displayOrder` | number | 展示顺序 |
| `stage` | string | `running` / `completed` / `failed` |
| `runStatus` | string | `running` / `success` / `failed` |
| `outputSummary` | string | 输出摘要 |
| `suggestedPrice` | number | 建议价 |
| `predictedProfit` | number | 预测利润 |
| `confidenceScore` | number | 置信度 |
| `riskLevel` | string | 风险等级 |
| `needManualReview` | boolean | 是否需要人工审核 |
| `thinking` | string | 用于前端展示的思考摘要 |
| `evidence` | `Array<Record<string, any>>` | 证据列表 |
| `suggestion` | `Record<string, any>` | 建议对象 |
| `reasonWhy` | string | 最终原因说明 |
| `createdAt` | string(datetime) | 创建时间 |

#### 2.5.2 额外说明

- `POST /api/decision/start` 现在虽然接收 `productIds` 数组，但当前实现实际只会使用第一个商品 ID 创建任务
- `POST /api/decision/apply/{resultId}` 成功后会直接把商品当前售价改成结果里的 `finalPrice`
- `GET /api/decision/export/{taskId}` 导出的文件名格式为 `DecisionReport_{taskId}.xlsx`

### 2.6 单商品定价任务桥接接口

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/pricing/tasks` | `POST` | Bearer | JSON：`PricingTaskCreateDTO` | `Result<number>` | 创建单商品任务 |
| `/api/pricing/tasks/{taskId}/cancel` | `POST` | Bearer | Path：`taskId` | `Result<null>` | 取消任务 |
| `/api/pricing/tasks/{taskId}` | `GET` | Bearer | Path：`taskId` | `Result<PricingTaskDetailVO>` | 任务详情 |
| `/api/pricing/tasks/{taskId}/snapshot` | `GET` | Bearer | Path：`taskId` | `Result<PricingTaskSnapshotVO>` | 一次性返回详情、日志、对比结果 |
| `/api/pricing/tasks/{taskId}/logs` | `GET` | Bearer | Path：`taskId` | `Result<DecisionLogVO[]>` | 任务日志 |
| `/api/pricing/tasks/{taskId}/events` | `GET` | Bearer | Path：`taskId` | `text/event-stream` | SSE 实时流 |

#### 2.6.1 对象定义

##### `PricingTaskCreateDTO`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `productId` | number | 是 | 商品 ID |
| `constraints` | string | 否 | 约束字符串 |
| `strategyGoal` | string | 否 | 为空时后端默认 `MAX_PROFIT` |

##### `PricingTaskDetailVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `taskId` | number | 任务 ID |
| `productId` | number | 商品 ID |
| `productTitle` | string | 商品标题 |
| `taskStatus` | string | 任务状态 |
| `currentPrice` | number | 当前价格 |
| `suggestedMinPrice` | number | 建议最低价 |
| `suggestedMaxPrice` | number | 建议最高价 |
| `finalPrice` | number | 最终建议价 |
| `expectedSales` | number | 预期销量 |
| `expectedProfit` | number | 预期利润 |
| `strategy` | string | 最终执行策略 |
| `finalSummary` | string | 最终摘要 |
| `createdAt` | string(datetime) | 创建时间 |
| `updatedAt` | string(datetime) | 更新时间 |

##### `PricingTaskSnapshotVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `detail` | `PricingTaskDetailVO` | 任务详情 |
| `logs` | `DecisionLogVO[]` | 日志列表 |
| `comparison` | `DecisionComparisonVO[]` | 结果对比列表 |

#### 2.6.2 SSE 事件格式

SSE 由 Java 发出，事件名固定为 `message`，消息体核心字段如下。

##### 通用字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schemaVersion` | string | 当前固定为 `1.0.0` |
| `channel` | string | 当前固定为 `pricing.task.card` |
| `type` | string | 事件类型 |
| `taskId` | number | 任务 ID |
| `timestamp` | string(datetime) | 事件时间 |

##### `task_started`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `task_started` |
| `status` | string | 当前任务状态 |

##### `agent_card`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `agent_card` |
| `agentCode` | string | `DATA_ANALYSIS` / `MARKET_INTEL` / `RISK_CONTROL` / `MANAGER_COORDINATOR` |
| `agentName` | string | 智能体名称 |
| `displayOrder` | number | 展示顺序 |
| `runAttempt` | number | 第几次尝试 |
| `stage` | string | `running` / `completed` / `failed` |
| `card` | object | 卡片内容 |

`card` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `thinking` | string | 思考摘要 |
| `evidence` | `Array<Record<string, any>>` | 证据列表 |
| `suggestion` | `Record<string, any>` | 建议对象 |
| `reasonWhy` | string \| null | 原因说明 |

##### `task_completed`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `task_completed` |
| `status` | string | `COMPLETED` 或 `MANUAL_REVIEW` |
| `result` | object | 结果摘要 |

`result` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `finalPrice` | number | 最终价格 |
| `expectedSales` | number | 预期销量 |
| `expectedProfit` | number | 预期利润 |
| `strategy` | string | 当前实现固定为 `人工审核` |
| `summary` | string | 结果摘要 |

##### `task_failed`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `task_failed` |
| `status` | string | `FAILED` / `CANCELLED` / `MANUAL_REVIEW` 等终态 |
| `message` | string | 失败或终止原因 |

### 2.7 批量定价

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/pricing/batches` | `POST` | Bearer | JSON：`PricingBatchCreateDTO` | `Result<PricingBatchCreateVO>` | 创建批量任务 |
| `/api/pricing/batches` | `GET` | Bearer | Query：`page=1`、`size=5`、`status?` | `Result<Page<PricingBatchDetailVO>>` | 最近批次列表 |
| `/api/pricing/batches/{batchId}` | `GET` | Bearer | Path：`batchId` | `Result<PricingBatchDetailVO>` | 批次详情 |
| `/api/pricing/batches/{batchId}/items` | `GET` | Bearer | Path：`batchId`，Query：`page=1`、`size=10`、`status?` | `Result<Page<PricingBatchItemVO>>` | 批次明细 |
| `/api/pricing/batches/{batchId}/cancel` | `POST` | Bearer | Path：`batchId` | `Result<PricingBatchCancelVO>` | 取消当前仍可取消的子任务 |

#### 2.7.1 对象定义

##### `PricingBatchCreateDTO`

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `productIds` | number[] | 是 | 至少 1 个，最多 50 个 | 商品 ID 列表 |
| `strategyGoal` | string | 是 | 非空，长度不超过 50 | 策略目标 |
| `constraints` | string | 否 | 长度不超过 1000 | 约束字符串 |

##### `PricingBatchCreateVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `batchId` | number | 批次 ID |
| `batchCode` | string | 批次编码 |
| `totalCount` | number | 商品总数 |
| `linkedTaskIds` | number[] | 成功关联的子任务 ID 列表 |
| `createFailedCount` | number | 创建失败数量 |

##### `PricingBatchDetailVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `batchId` | number | 批次 ID |
| `batchCode` | string | 批次编码 |
| `batchStatus` | string | 批次状态 |
| `strategyGoal` | string | 策略目标 |
| `constraintText` | string | 约束文本 |
| `totalCount` | number | 总商品数 |
| `runningCount` | number | 运行中数量 |
| `completedCount` | number | 已完成数量 |
| `manualReviewCount` | number | 人工审核数量 |
| `failedCount` | number | 失败数量 |
| `cancelledCount` | number | 取消数量 |
| `finalizedAt` | string(datetime) | 批次结束时间 |
| `createdAt` | string(datetime) | 创建时间 |
| `updatedAt` | string(datetime) | 更新时间 |

##### `PricingBatchItemVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 批次项 ID |
| `batchId` | number | 批次 ID |
| `itemOrder` | number | 顺序号 |
| `productId` | number | 商品 ID |
| `taskId` | number | 子任务 ID |
| `resultId` | number | 结果 ID |
| `productTitle` | string | 商品标题 |
| `currentPrice` | number | 当前价格 |
| `finalPrice` | number | 最终价格 |
| `expectedSales` | number | 预期销量 |
| `expectedProfit` | number | 预期利润 |
| `profitGrowth` | number | 利润增长值 |
| `creationStatus` | string | 创建状态，常见 `TASK_LINKED` / `CREATE_FAILED` |
| `taskStatus` | string | 子任务状态 |
| `displayStatus` | string | 明细展示状态 |
| `executeStrategy` | string | 执行策略 |
| `reviewRequired` | boolean | 是否需要人工审核 |
| `appliedStatus` | string | `已应用` / `未应用` |
| `errorMessage` | string | 错误信息 |
| `createdAt` | string(datetime) | 创建时间 |
| `batchItemUpdatedAt` | string(datetime) | 批次项更新时间 |
| `taskUpdatedAt` | string(datetime) | 子任务更新时间 |
| `updatedAt` | string(datetime) | 当前返回对象更新时间 |

##### `PricingBatchCancelVO`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `cancelledCount` | number | 成功取消数量 |
| `skippedCount` | number | 跳过数量 |

### 2.8 健康检查与指标

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/api/health` | `GET` | 否 | 无 | `JavaReadyHealth` | 等同于 `/api/health/ready` |
| `/api/health/live` | `GET` | 否 | 无 | `JavaLiveHealth` | 存活检查 |
| `/api/health/ready` | `GET` | 否 | 无 | `JavaReadyHealth` | 就绪检查 |
| `/api/health/metrics` | `GET` | 否 | 无 | `JavaMetricsHealth` | 任务统计指标 |

#### 2.8.1 对象定义

##### `JavaLiveHealth`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 固定为 `ok` |

##### `JavaReadyHealth`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ok` / `degraded` |
| `database` | string | `ok` / `down` |
| `pythonWorker` | string | `ok` / `down` |
| `rabbitmq` | string | `ok` / `down` |

##### `JavaMetricsHealth`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 与 ready 接口一致 |
| `tasks` | object | 任务指标快照 |

`tasks` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `total` | number | 总任务数 |
| `queued` | number | 排队中数量 |
| `retrying` | number | 重试中数量 |
| `running` | number | 执行中数量 |
| `queueDepth` | number | `queued + retrying` |
| `activeExecutions` | number | 当前执行中数量 |
| `completed` | number | 已完成数量 |
| `manualReview` | number | 人工审核数量 |
| `failed` | number | 失败数量 |
| `cancelled` | number | 已取消数量 |
| `staleRunningTasks` | number | 长时间运行中的任务数 |
| `avgDurationSeconds` | number | 平均耗时（秒） |
| `maxDurationSeconds` | number | 最大耗时（秒） |
| `latestTaskCreatedAt` | string(datetime) \| null | 最新任务创建时间 |

## 3. Python 内部 API

说明：

- 默认前缀：`/internal`
- 当前路由来自 `backend-python/app/main.py`：
  - `app.include_router(health_router)`
  - `app.include_router(internal_tasks_router, prefix=settings.python_base_prefix)`
- 响应头会带 `X-Trace-Id`
- `internal-tasks` 路由全部依赖 `X-Internal-Token`

### 3.1 内部任务接口

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/internal/tasks/{taskId}/status` | `GET` | `X-Internal-Token` | Path：`taskId` | `TaskStatusResponse` | 查询任务状态 |
| `/internal/tasks/{taskId}/detail` | `GET` | `X-Internal-Token` | Path：`taskId` | `TaskDetailResponse` | 查询任务详情 |
| `/internal/tasks/{taskId}/logs` | `GET` | `X-Internal-Token` | Path：`taskId`，Query：`limit=200`，范围 `1-1000` | `TaskLogsResponse` | 查询日志 |
| `/internal/tasks/{taskId}/retry` | `POST` | `X-Internal-Token` | Path：`taskId`，JSON：`RetryTaskRequest` | `DispatchTaskResponse` | 重试指定任务 |

#### 3.1.1 对象定义

##### `TaskStatusResponse`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `taskId` | number | 任务 ID |
| `status` | string | 任务状态 |
| `hasResult` | boolean | 是否已有结果 |
| `message` | string \| null | 说明消息 |

##### `RetryTaskRequest`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `productId` | number | 否 | 可选覆盖原商品 ID |
| `strategyGoal` | string | 否 | 可选覆盖原策略目标 |
| `constraints` | string | 否 | 可选覆盖原约束 |

##### `DispatchTaskResponse`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `accepted` | boolean | 是否已接受 |
| `taskId` | number | 任务 ID |
| `status` | string | 当前状态 |
| `message` | string \| null | 说明消息 |

##### `TaskResultBrief`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `finalPrice` | number | 最终价格 |
| `expectedSales` | number \| null | 预期销量 |
| `expectedProfit` | number | 预期利润 |
| `profitGrowth` | number | 利润增长值 |
| `isPass` | boolean | 是否通过 |
| `executeStrategy` | string \| null | 执行策略 |
| `resultSummary` | string \| null | 结果摘要 |

##### `TaskDetailResponse`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `taskId` | number | 任务 ID |
| `status` | string | 任务状态 |
| `productId` | number | 商品 ID |
| `currentPrice` | number | 当前价格 |
| `suggestedMinPrice` | number \| null | 建议最低价 |
| `suggestedMaxPrice` | number \| null | 建议最高价 |
| `createdAt` | string(datetime) | 创建时间 |
| `updatedAt` | string(datetime) | 更新时间 |
| `hasResult` | boolean | 是否已有结果 |
| `result` | `TaskResultBrief \| null` | 结果摘要 |

##### `TaskLogsResponse`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `taskId` | number | 任务 ID |
| `total` | number | 日志条数 |
| `logs` | `AgentLogItem[]` | 日志列表 |

##### `AgentLogItem`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 日志 ID |
| `taskId` | number | 任务 ID |
| `roleName` | string | 角色名 |
| `speakOrder` | number | 说话顺序 |
| `thoughtContent` | string \| null | 思考内容 |
| `agentCode` | string \| null | 智能体代码 |
| `agentName` | string \| null | 智能体名称 |
| `runAttempt` | number \| null | 尝试次数 |
| `runOrder` | number \| null | 运行顺序 |
| `displayOrder` | number \| null | 展示顺序 |
| `stage` | string \| null | 阶段 |
| `runStatus` | string \| null | 运行状态 |
| `outputSummary` | string \| null | 输出摘要 |
| `outputPayload` | `Record<string, any> \| null` | 原始输出 |
| `suggestedPrice` | number \| null | 建议价 |
| `predictedProfit` | number \| null | 预测利润 |
| `confidenceScore` | number \| null | 置信度 |
| `riskLevel` | string \| null | 风险等级 |
| `needManualReview` | boolean \| null | 是否需要人工审核 |
| `thinking` | string \| null | 思考摘要 |
| `evidence` | `Array<Record<string, any>> \| null` | 证据列表 |
| `suggestion` | `Record<string, any> \| null` | 建议对象 |
| `reasonWhy` | string \| null | 原因说明 |
| `createdAt` | string(datetime) | 创建时间 |

### 3.2 Python 健康检查

| 接口 | 方法 | 鉴权 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `/health` | `GET` | 否 | 无 | `PythonHealthResponse` | 基础健康检查 |
| `/health/live` | `GET` | 否 | 无 | `PythonLiveHealth` | 存活检查 |
| `/health/ready` | `GET` | 否 | 无 | `PythonReadyHealth` | 就绪检查 |
| `/health/metrics` | `GET` | 否 | 无 | `PythonMetricsHealth` | 指标快照 |

#### 3.2.1 对象定义

##### `PythonHealthResponse`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ok` / `degraded` |
| `db_ok` | boolean | 数据库是否可用 |

##### `RabbitMqWorkerSnapshot`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `started` | boolean | Worker 是否已启动 |
| `ready` | boolean | Worker 是否 ready |
| `prefetch` | number | RabbitMQ prefetch |
| `maxRetry` | number | 最大消费重试次数 |

##### `PythonLiveHealth`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 固定为 `ok` |
| `rabbitmq` | `RabbitMqWorkerSnapshot` | Worker 快照 |

##### `PythonReadyHealth`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ok` / `degraded` |
| `dbOk` | boolean | 数据库是否可用 |
| `rabbitmq` | string | `ok` / `down` |
| `worker` | `RabbitMqWorkerSnapshot` | Worker 快照 |

##### `PythonMetricsHealth`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ok` / `degraded` |
| `dbOk` | boolean | 数据库是否可用 |
| `rabbitmq` | string | `ok` / `down` |
| `worker` | `RabbitMqWorkerSnapshot` | Worker 快照 |
| `tasks` | object | 任务指标快照 |

`tasks` 字段与 Java `metrics.tasks` 基本同构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `total` | number | 总任务数 |
| `queued` | number | 排队中数量 |
| `retrying` | number | 重试中数量 |
| `running` | number | 运行中数量 |
| `queueDepth` | number | `queued + retrying` |
| `activeExecutions` | number | 当前执行中数量 |
| `completed` | number | 已完成数量 |
| `manualReview` | number | 人工审核数量 |
| `failed` | number | 失败数量 |
| `cancelled` | number | 已取消数量 |
| `staleRunningTasks` | number | 长时间运行中的任务数 |
| `avgDurationSeconds` | number | 平均耗时 |
| `maxDurationSeconds` | number | 最大耗时 |
| `latestTaskCreatedAt` | string(datetime) \| null | 最新任务创建时间 |

## 4. 前端调用与后端契约补充

### 4.1 Axios 公共行为

- `frontend/src/api/request.ts` 统一配置：
  - `baseURL = /api`
  - `withCredentials = true`
  - 自动附加 `Authorization: Bearer <token>`
  - `401` 时尝试调用 `/api/user/refresh`

### 4.2 SSE 连接方式

前端当前使用：

- `GET /api/pricing/tasks/{taskId}/events`
- 请求头：
  - `Accept: text/event-stream`
  - `Authorization: Bearer <token>`
- 额外配置：
  - `credentials: include`

### 4.3 当前最重要的真实契约点

- 浏览器不要直连 Python；前端只应访问 `/api/**`
- `strategyGoal` 当前前端值使用：
  - `MAX_PROFIT`
  - `CLEARANCE`
  - `MARKET_SHARE`
- `constraints` 当前是“字符串化 JSON”，不是对象
- `/api/decision/start` 仍保留多商品数组形态，但当前实现只实际处理第一个商品
- 单商品实时任务的最终 `strategy` 当前实现会固定落成“人工审核”
