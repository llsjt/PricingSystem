from app.schemas.decision import FinalDecision, AgentSummary
from typing import List

class ReportGenerator:
    """
    ReportGenerator（报告生成工具）
    职责：
    - 将结构化的决策结果转换为可读性强的 Markdown 文本报告
    - 供 ManagerCoordinatorAgent 调用，或后续导出 PDF 使用
    """

    @staticmethod
    def generate_markdown_report(
        product_name: str,
        current_price: float,
        decision: FinalDecision
    ) -> str:
        """
        生成标准 Markdown 决策报告
        :param product_name: 商品名称
        :param current_price: 当前售价
        :param decision: 最终决策对象
        :return: Markdown 格式字符串
        """
        
        # 1. 提取各 Agent 的摘要
        data_summary = ReportGenerator._find_summary(decision.agent_summaries, "DataAnalysisAgent")
        market_summary = ReportGenerator._find_summary(decision.agent_summaries, "MarketIntelAgent")
        risk_summary = ReportGenerator._find_summary(decision.agent_summaries, "RiskControlAgent")
        
        # 2. 计算建议价格
        suggested_price = current_price * decision.discount_rate
        
        # 3. 组装 Markdown
        report = f"""
# 🛒 智能定价决策报告

**商品名称**: {product_name}  
**当前售价**: ¥{current_price:.2f}  
**决策时间**: (系统生成时间)

---

## 📊 1. 综合决策结论
> **{decision.decision}**

- **建议折扣率**: {decision.discount_rate * 10: .1f}折 ({(1-decision.discount_rate)*100:.0f}% OFF)
- **建议执行价**: ¥{suggested_price:.2f}
- **决策置信度**: {decision.confidence * 100:.0f}%

---

## 💡 2. 核心决策依据
{decision.core_reasons}

---

## 🔍 3. 多维度分析摘要

### 📈 数据洞察 (Data Insight)
{data_summary}

### 🛍️ 市场情报 (Market Intel)
{market_summary}

### 🛡️ 风险控制 (Risk Control)
{risk_summary}

---

## ⚠️ 4. 风险提示
> {decision.risk_warning}

---
*本报告由智能电商决策支持系统自动生成，仅供参考。*
"""
        return report.strip()

    @staticmethod
    def _find_summary(summaries: List[AgentSummary], agent_name: str) -> str:
        """
        从摘要列表中查找指定 Agent 的摘要
        """
        for s in summaries:
            if s.agent_name == agent_name:
                return s.summary
        return "暂无分析数据"
