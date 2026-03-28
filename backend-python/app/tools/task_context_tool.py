from app.schemas.agent import ProductContext


class TaskContextTool:
    def build_summary(self, product: ProductContext, strategy_goal: str, constraints: dict) -> str:
        return (
            f"商品={product.product_name}, 当前价={product.current_price}, 成本={product.cost_price}, "
            f"库存={product.stock}, 目标={strategy_goal}, 约束={constraints}"
        )

