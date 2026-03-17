**1. 前端 (Frontend)**

- **核心**: Vue.js 3.4+ (必须使用 `<script setup>` 语法糖), TypeScript.
- **状态管理**: Pinia (禁止使用 Vuex).
- **网络请求**: Axios (需封装统一的 Request/Response 拦截器).
- **可视化**: ECharts.
- **UI 规范**: 组件命名采用 PascalCase (大驼峰), 文件命名采用 kebab-case (短横线).

**2. 后端 (Backend)**

- **核心**: Spring Boot 3.2+, JDK 21.
- **ORM**: MyBatis-Plus (禁止使用原生 JDBC 或 Hibernate).
- **工具**: Lombok (简化 Getter/Setter/Builder).
- **通信**: RESTful API 为主，实时通知使用 WebSocket.
- **规范**: 实体类使用 Lombok `@Data`, Controller 层统一返回 `Result<T>` 泛型结构.

**3. AI Agent (Python)**

- **核心**: Python 3.10+, FastAPI.
- **框架**: LangChain (用于链式调用), CrewAI (用于多智能体协作).
- **接口**: 所有 Agent 功能必须暴露为 HTTP API 供后端调用.

**4. 基础设施 (Infrastructure)**

- **数据库**: MySQL 8.0+ (使用 InnoDB 引擎).
- **缓存**: Redis 7.0+.
- **向量库**: 使用 Chroma&#x20;

**代码风格与架构规范**

- **缩进**: 统一使用 4 个空格 (Java/Python) 或 2 个空格 (Vue/TS).
- **命名**:
  - Java: CamelCase (驼峰式), 常量 UPPER\_SNAKE\_CASE.
  - Python: snake\_case (下划线式).
  - TS/Vue: CamelCase (变量/函数), PascalCase (组件/类).
- **分层架构**:
  - 后端严格遵循 Controller -> Service -> Mapper/Repository 分层.
  - 前端严格遵循 View -> Composable/Hooks -> API -> Store 分层.
- **依赖注入**: 后端必须使用 Spring 的 `@Autowired` 或构造器注入; 前端使用 Composition API 的组合式函数.

**特殊指令**

- 当生成数据库相关代码时，必须同时提供对应的 SQL 建表语句。
- 当涉及跨服务调用（如 Spring Boot 调用 Python Agent）时，必须定义清晰的 DTO (数据传输对象)。
- 遇到不确定的配置，优先选择官方文档推荐的“最佳实践”而非过时教程。

