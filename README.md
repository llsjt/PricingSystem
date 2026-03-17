# 智能电商定价决策系统

基于多智能体协作（Multi-Agent）的电商自动定价模拟平台。系统模拟真实的电商运营场景，通过爬取/导入商品数据，利用大语言模型（如 Qwen-Plus）扮演不同角色（数据分析师、财务风控官、市场策略官等）进行辩论，最终输出科学的定价策略。

## 功能特性

1. **商品数据管理**：支持 Excel 批量导入商品历史经营数据（访客、销量、转化率等），支持手动录入。
2. **多智能体决策实验室**：勾选商品，设定策略目标（如清仓大甩卖、利润最大化）和约束条件，启动决策。
3. **Agent 辩论可视化**：通过 WebSocket 实时推送多角色 Agent 的思考和辩论过程。
4. **决策档案与回溯**：记录历史决策结果，提供前后价格及利润的直观对比图表，支持一键应用价格到商品库或导出报告。
5. **系统配置管理**：动态配置 API Key、默认利润阈值及 Agent 模型，无需重启即刻生效。

## 技术架构

- **前端**：Vue 3 + TypeScript + Element Plus + ECharts + Pinia
- **后端 (Java)**：Spring Boot 3 + MyBatis-Plus + MySQL 8.0 (主业务逻辑与数据存储)
- **Agent 服务 (Python)**：FastAPI + OpenAI 兼容接口 (DashScope) + SQLAlchemy (大模型调用与多智能体编排)

## 本地启动步骤

### 1. 数据库准备
1. 安装 MySQL 8.0+。
2. 执行 `database/schema.sql` 初始化数据库和表。
3. 默认数据库名：`pricing_system`。

### 2. 后端 Java 服务启动
1. 进入 `backend-java` 目录。
2. 修改 `src/main/resources/application.yml` 中的数据库用户名和密码（默认为 root / 123456）。
3. 运行 `PricingBackendApplication.java` 或使用 Maven: `mvn spring-boot:run`。
4. 服务默认启动在 `8080` 端口。

### 3. Agent Python 服务启动
1. 进入 `backend-python` 目录。
2. 创建虚拟环境并激活：`python -m venv .venv`，`source .venv/Scripts/activate` (Windows)。
3. 安装依赖：`pip install -r requirements.txt`。
4. 启动服务：`uvicorn main:app --reload --port 8000`。
5. (可选) 配置 `.env` 文件中的 `DASHSCOPE_API_KEY`，或在前端系统设置页面配置。

### 4. 前端 Vue 服务启动
1. 进入 `frontend` 目录。
2. 安装依赖：`npm install`。
3. 启动开发服务器：`npm run dev`。
4. 访问 `http://localhost:5173`。

## 功能演示指南

1. **如何导入数据**：进入【数据导入与管理】页面，点击【下载模板】，填写数据后上传。
2. **如何发起决策**：进入【智能定价实验室】，勾选需要调整的商品，选择策略（如“利润最大化”），填写约束条件，点击【开始生成定价策略】。
3. **如何查看辩论**：发起决策后，页面右侧将实时展示多个 Agent 角色基于商品数据的分析和辩论过程。
4. **如何应用价格**：进入【决策档案】，点击某次任务的【查看详情】，在对比列表中点击【应用】即可将建议价格更新到实际商品中。

## 常见问题排查 (FAQ)

1. **Agent 辩论无响应或报错？**
   - 检查前端【系统设置】中是否配置了有效的阿里云 DashScope API Key。
   - 检查 Python 后端服务是否正常运行 (端口 8000)。
2. **数据库连接失败？**
   - 确认 MySQL 服务已启动，且 `application.yml` 中的密码正确。
3. **上传 Excel 失败？**
   - 确保使用的是下载的模板格式，且必填字段（标题、成本价、售价）不为空。

## 测试自测清单

- [x] 上传错误格式 Excel 是否提示？
- [x] Python Agent 接口超时或调用失败是否重试？(已通过 tenacity/重试机制处理)
- [x] 在档案页点击“应用”后，数据库 biz_product 表 current_price 是否变更？
- [x] 档案列表是否能按状态或策略类型正确筛选？
- [x] 修改 API Key 后是否无需重启 Python 服务即可生效？(已实现每次调用时从 DB 读取)
