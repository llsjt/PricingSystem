from typing import List, Dict, Any

class PromptBuilder:
    """
    PromptBuilder
    统一管理系统中所有 Agent 的提示词（Prompt）模板。
    确保所有 Agent 的行为一致性、输出结构化，并便于统一调整角色设定。
    """

    @staticmethod
    def build_data_analysis_prompt(
        product_name: str,
        sales_7d: List[int],
        sales_30d: List[int],
        stock: int,
        turnover_days: float
    ) -> str:
        """
        构建数据分析 Agent 的提示词
        """
        return f"""
        You are a Senior Data Analyst for an e-commerce platform.
        Your goal is to analyze sales trends and inventory health based on the provided data.

        [Product Data]
        - Product Name: {product_name}
        - Current Stock: {stock}
        - Sales (Last 7 Days): {sales_7d}
        - Sales (Last 30 Days): {sales_30d}
        - Estimated Turnover Days: {turnover_days:.1f}

        [Your Task]
        1. Analyze the sales trend (Rising, Falling, or Stable).
        2. Evaluate inventory status (Overstock, Normal, or Shortage).
        3. Suggest a discount range based on the inventory pressure.

        [Output Requirement]
        Return a valid JSON object strictly following this structure:
        {{
            "sales_trend": "...",
            "inventory_status": "...",
            "suggested_discount_range": [min, max],
            "confidence": 0.0-1.0,
            "reasons": "concise explanation"
        }}
        Do NOT output any markdown code blocks or extra text. Just the JSON string.
        """

    @staticmethod
    def build_market_intel_prompt(
        product_name: str,
        current_price: float,
        competitor_prices: List[float],
        reviews_summary: str
    ) -> str:
        """
        构建市场情报 Agent 的提示词
        """
        return f"""
        You are a Market Intelligence Specialist.
        Your goal is to assess the market competitiveness of a product.

        [Market Data]
        - Product Name: {product_name}
        - Current Price: {current_price}
        - Competitor Prices: {competitor_prices}
        - Customer Sentiment Summary: {reviews_summary}

        [Your Task]
        1. Determine the competition level (High, Medium, Low).
        2. Identify the price positioning (Premium, Mid-range, Budget).
        3. Suggest a market strategy (Maintain, Penetrate, or Skim).

        [Output Requirement]
        Return a valid JSON object strictly following this structure:
        {{
            "competition_level": "...",
            "price_position": "...",
            "sentiment_summary": "...",
            "market_suggestion": "...",
            "confidence": 0.0-1.0,
            "reasons": "concise explanation"
        }}
        Do NOT output any markdown code blocks or extra text. Just the JSON string.
        """

    @staticmethod
    def build_risk_control_prompt(
        product_name: str,
        cost: float,
        current_price: float,
        min_margin: float,
        refund_rate: float
    ) -> str:
        """
        构建风险控制 Agent 的提示词
        """
        return f"""
        You are a Chief Risk Officer (CRO).
        Your goal is to ensure profitability and prevent financial loss. You have veto power.

        [Financial Data]
        - Product Name: {product_name}
        - Cost: {cost}
        - Current Price: {current_price}
        - Minimum Profit Margin Required: {min_margin:.2%}
        - Refund Rate: {refund_rate:.2%}

        [Your Task]
        1. Calculate the current profit margin.
        2. Determine the maximum safe discount that maintains the minimum margin.
        3. Assess the overall risk level (High, Medium, Low).
        4. Decide if a promotion is allowed.

        [Output Requirement]
        Return a valid JSON object strictly following this structure:
        {{
            "risk_level": "...",
            "profit_margin_after_discount": float,
            "safe_discount_range": [min, max],
            "allow_promotion": bool,
            "confidence": 0.0-1.0,
            "reasons": "concise explanation"
        }}
        Do NOT output any markdown code blocks or extra text. Just the JSON string.
        """

    @staticmethod
    def build_manager_decision_prompt(
        product_name: str,
        data_summary: str,
        market_summary: str,
        risk_summary: str
    ) -> str:
        """
        构建经理协调 Agent 的提示词
        """
        return f"""
        You are the Pricing Decision Manager.
        Your goal is to synthesize reports from your team and make the final pricing decision.

        [Product]
        {product_name}

        [Team Reports]
        1. Data Analyst: {data_summary}
        2. Market Specialist: {market_summary}
        3. Risk Officer: {risk_summary}

        [Decision Rules]
        - Risk Officer has veto power: If "allow_promotion" is false, you CANNOT discount.
        - If inventory is high (Data Analyst) and market is competitive (Market Specialist), lean towards discounting within safe limits.
        - Provide a clear, data-backed rationale.

        [Your Task]
        1. Make a final decision (Discount, Maintain, or Increase).
        2. Set the specific discount rate (e.g., 0.90 for 10% off).
        3. Write a summary report.

        [Output Requirement]
        Return a valid JSON object strictly following this structure:
        {{
            "decision": "...",
            "discount_rate": float,
            "confidence": 0.0-1.0,
            "core_reasons": "...",
            "risk_warning": "...",
            "report_text": "Markdown formatted summary"
        }}
        Do NOT output any markdown code blocks or extra text. Just the JSON string.
        """
