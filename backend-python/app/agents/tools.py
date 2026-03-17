from langchain.tools import tool
from app.services.mock_data import mock_service

class ProductTools:
    @tool("Get Product Information")
    def get_product_info(product_id: str):
        """获取指定商品的基础信息，包括名称、价格、成本、库存等。"""
        return mock_service.get_product_info(product_id).model_dump_json()

    @tool("Get Sales History")
    def get_sales_history(product_id: str):
        """获取指定商品过去30天的销量数据。"""
        return str(mock_service.get_sales_history(product_id))

    @tool("Get Competitor Analysis")
    def get_competitors(product_id: str):
        """获取指定商品的竞品信息，包括价格、销量和评分。"""
        return str([c.model_dump() for c in mock_service.get_competitors(product_id)])
