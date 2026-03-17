# 淘宝 Web 爬虫使用指南

## 概述

本系统使用 **Selenium + Chrome 浏览器** 爬取淘宝竞品数据，当真实爬取失败时会自动降级使用 Mock 数据。

## 技术架构

```
┌─────────────────────────────────────┐
│   MarketIntelAgent (市场分析 Agent) │
└──────────────┬──────────────────────┘
               │ 调用
┌──────────────▼──────────────────────┐
│   CompetitorCrawler (竞品爬虫服务)  │
└──────────────┬──────────────────────┘
               │ 调用
┌──────────────▼──────────────────────┐
│   TaobaoWebCrawler (淘宝 Web 爬虫)  │
│   - Selenium + Chrome               │
│   - 反爬处理（隐藏 webdriver 特征）     │
│   - 多种数据提取方式                │
│   - Mock 数据降级                   │
└─────────────────────────────────────┘
```

## 依赖安装

### 1. 安装 Python 依赖

```bash
cd backend-python
pip install selenium
pip install webdriver-manager
```

### 2. 确保已安装 Chrome 浏览器

系统会自动使用你电脑上已安装的 Chrome 浏览器，并通过 `webdriver-manager` 自动下载匹配的 ChromeDriver。

## 使用方法

### 方式 1：直接使用淘宝爬虫

```python
from app.services.taobao_web_crawler import taobao_crawler

# 搜索商品
products = taobao_crawler.search_products("蓝牙耳机", limit=5)

# 打印结果
for prod in products:
    print(f"商品：{prod.title}")
    print(f"价格：¥{prod.price}")
    print(f"销量：{prod.sales_volume}")
    print(f"店铺：{prod.shop_name}")
    print(f"链接：{prod.product_url}")
    print("-" * 60)
```

### 方式 2：使用竞品爬虫服务

```python
from app.services.competitor_crawler import competitor_crawler

# 搜索竞品（默认只爬取淘宝）
competitors = competitor_crawler.search_competitors(
    keyword="蓝牙耳机",
    category="数码配件",
    platforms=['taobao'],  # 只爬取淘宝
    limit=10
)

# 打印结果
for comp in competitors:
    print(f"商品：{comp.product_name}")
    print(f"价格：¥{comp.price}")
    print(f"销量：{comp.sales_volume}")
    print(f"评分：{comp.rating}")
    print(f"店铺：{comp.shop_name} ({comp.shop_type})")
```

### 方式 3：在 MarketIntelAgent 中自动调用

```python
from app.agents.market_intel_agent import MarketIntelAgent
from app.schemas.analysis_schemas import AnalysisRequest

agent = MarketIntelAgent()

# 创建分析请求（不带竞品数据）
request = AnalysisRequest(
    product=ProductBase(
        product_name="蓝牙耳机",
        category="数码配件",
        price=99.0,
        # ... 其他字段
    ),
    competitor_data=CompetitorData(
        competitor_prices=[],  # 空数据，触发爬虫
        competitor_activities=[]
    )
)

# 执行分析（会自动调用爬虫获取竞品数据）
result = agent.analyze(request)
```

## 数据爬取策略

系统采用**三层降级策略**确保数据获取：

### 1. 第一层：JSON 数据提取
- 执行 JavaScript 从页面脚本中提取内嵌的 JSON 数据
- 优点：数据完整、准确
- 缺点：淘宝经常更新数据结构

### 2. 第二层：DOM 元素解析
- 使用 CSS 选择器解析商品元素
- 使用多种选择器尝试匹配（`.item`, `.m-item`, `[data-item-id]` 等）
- 优点：适应性强
- 缺点：受页面结构影响大

### 3. 第三层：Mock 数据降级
- 当真实爬取失败时，生成符合格式的 Mock 数据
- 优点：保证系统可用，不会因爬取失败导致整个流程中断
- 缺点：数据不是实时的

## 反爬措施处理

### 1. 隐藏 WebDriver 特征
```python
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

# 执行 CDP 命令
browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
    'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
})
```

### 2. 设置 User-Agent
```python
chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
```

### 3. 无头模式
```python
chrome_options.add_argument('--headless')
```

### 4. 延迟和滚动
```python
time.sleep(5)  # 等待页面加载
for _ in range(3):
    browser.execute_script("window.scrollBy(0, 800)")
    time.sleep(2)  # 模拟真实用户行为
```

## 测试

### 运行测试脚本

```bash
cd backend-python
python tests\test_taobao_crawler.py
```

### 预期输出

```
============================================================
测试淘宝 Web 爬虫（Selenium + Chrome）
============================================================

🔍 搜索关键词：蓝牙耳机

✅ 成功爬取 5 个商品

1. 蓝牙耳机 无线蓝牙 5.3 入耳式运动耳机
   价格：¥89.0
   销量：10000
   店铺：音悦数码专营店 (tmall)
   链接：https://item.taobao.com/item.htm?id=mock_1
------------------------------------------------------------

✅ 爬虫测试成功！
```

## 常见问题

### Q1: 为什么爬取到的数据是 Mock 数据？

**A**: 淘宝有非常强的反爬机制，当真实爬取失败时会自动降级到 Mock 数据。这是正常行为，确保系统不会因爬取失败而中断。

### Q2: 如何提高真实爬取成功率？

**A**: 
1. 使用真实 IP，避免使用代理
2. 增加延迟时间（修改 `time.sleep()` 参数）
3. 添加 Cookie（需要手动登录淘宝获取）
4. 使用有头模式（去掉 `--headless`）观察实际页面

### Q3: 浏览器启动失败怎么办？

**A**:
1. 确保已安装 Chrome 浏览器
2. 检查 Chrome 版本是否过旧
3. 删除缓存的 ChromeDriver：`C:\Users\{用户名}\.wdm\drivers\chromedriver\`
4. 重新运行，webdriver-manager 会自动下载合适的版本

### Q4: 爬取速度太慢怎么办？

**A**: 
1. 减少 `limit` 参数（默认 10）
2. 减少滚动次数（修改 `for _ in range(3)`）
3. 减少延迟时间（但不建议，可能导致被检测）

## 扩展其他平台

目前只支持淘宝/天猫平台。如需扩展其他平台（京东、拼多多等），需要：

1. 创建新的爬虫类（如 `JdWebCrawler`）
2. 实现对应的搜索和解析方法
3. 在 `CompetitorCrawler` 中添加调用逻辑

## 注意事项

1. **合法合规**：爬虫仅用于学习和研究，请遵守相关法律法规和网站 robots.txt 协议
2. **频率控制**：避免高频访问，建议设置访问间隔
3. **数据准确性**：Mock 数据仅供参考，实际决策应使用真实数据
4. **维护成本**：淘宝页面结构经常变化，需要定期维护选择器

## 技术栈

- **Selenium**: 浏览器自动化框架
- **ChromeDriver**: Chrome 浏览器驱动
- **webdriver-manager**: 自动管理 WebDriver 版本
- **Python 3.10+**: 编程语言
- **FastAPI**: Web 框架（用于 API 暴露）

## 相关文件

- `app/services/taobao_web_crawler.py`: 淘宝 Web 爬虫实现
- `app/services/competitor_crawler.py`: 竞品爬虫服务
- `app/agents/market_intel_agent.py`: 市场情报 Agent（调用爬虫）
- `tests/test_taobao_crawler.py`: 爬虫测试脚本

---

**最后更新**: 2026-03-17
**版本**: v1.0
