# Smart Pricing Lab - 部署指南

## 1. 环境准备 (Prerequisites)

- **OS**: Windows / Linux / macOS
- **Java**: JDK 21+
- **Python**: Python 3.10+
- **Node.js**: v18+
- **Database**: MySQL 8.0+
- **Cache**: Redis 7.0+
- **Vector DB**: ChromaDB (本地运行或 Docker)

## 2. 数据库初始化 (Database Setup)

1. 创建数据库 `pricing_system`。
2. 执行初始化脚本 `database/schema.sql`。
   ```bash
   mysql -u root -p pricing_system < database/schema.sql
   ```
3. 验证表结构是否创建成功 (`biz_product`, `dec_task`, `dec_result` 等)。

## 3. 后端服务部署 (Backend Services)

### 3.1 Java Backend (Spring Boot)
1. 进入 `backend-java` 目录。
2. 修改 `src/main/resources/application.yml` 中的数据库配置。
3. 启动服务：
   ```bash
   ./mvnw spring-boot:run
   # 或构建 Jar 包运行
   java -jar target/pricing-backend-0.0.1-SNAPSHOT.jar
   ```
4. 服务运行在端口 `8080`。

### 3.2 Python Agent Backend (FastAPI)
1. 进入 `backend-python` 目录。
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
3. 配置 `.env` 文件 (参考 `.env.example`)。
4. 启动服务：
   ```bash
   python main.py
   # 或使用 uvicorn
   uvicorn main:app --reload --port 8000
   ```
5. 服务运行在端口 `8000`。

## 4. 前端部署 (Frontend)

1. 进入 `frontend` 目录。
2. 安装依赖：
   ```bash
   npm install
   ```
3. 启动开发服务器：
   ```bash
   npm run dev
   ```
4. 访问 `http://localhost:5173`。

## 5. 验证部署 (Verification)

1. 打开浏览器访问前端页面。
2. 进入“智能定价实验室”模块。
3. 选择商品，配置策略，点击“启动智能决策”。
4. 观察右侧聊天窗口是否有 Agent 思考日志输出。
5. 等待任务完成，查看最终定价结果表格。

## 6. 常见问题 (Troubleshooting)

- **WebSocket 连接失败**: 检查 Python 服务是否启动，端口 8000 是否被防火墙拦截。
- **任务一直 Pending**: 检查 Java 后端日志，确认是否成功调用了 Python 服务的 `/api/decision/start` 接口。
- **数据库连接错误**: 检查 `application.yml` 和 `.env` 中的数据库账号密码是否一致。
