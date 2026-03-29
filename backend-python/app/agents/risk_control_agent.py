from decimal import Decimal

from app.schemas.agent import RiskAgentOutput
from app.tools.risk_rule_tool import RiskRuleTool
from app.utils.math_utils import money


class RiskControlAgent:
    code = "RISK_CONTROL"
    name = "风险控制Agent"

    def __init__(self) -> None:
        self.rule_tool = RiskRuleTool()

    def run(
        self,
        current_price: Decimal,
        cost_price: Decimal,
        candidate_price: Decimal,
        constraints: dict,
    ) -> RiskAgentOutput:
        evaluated = self.rule_tool.evaluate(
            current_price=money(current_price),
            cost_price=money(cost_price),
            candidate_price=money(candidate_price),
            constraints=constraints,
        )
        return RiskAgentOutput(
            isPass=bool(evaluated["is_pass"]),
            safeFloorPrice=money(evaluated["safe_floor_price"]),
            suggestedPrice=money(evaluated["suggested_price"]),
            riskLevel=str(evaluated["risk_level"]),
            needManualReview=bool(evaluated["need_manual_review"]),
            summary=(
                f"安全底价 {money(evaluated['safe_floor_price'])}，"
                f"风控建议价 {money(evaluated['suggested_price'])}，"
                f"结果 {'通过' if evaluated['is_pass'] else '需人工复核'}。"
            ),
        )
