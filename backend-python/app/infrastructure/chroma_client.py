import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from app.core.config import settings

class ChromaClient:
    """
    ChromaClient
    用于管理 Chroma 向量数据库连接，支持文本嵌入的存储与语义检索。
    主要用于：
    1. 存储和检索用户评论/舆情 (MarketIntelAgent 使用)
    2. 存储和检索历史决策报告 (ManagerCoordinatorAgent 使用 RAG)
    """

    def __init__(self):
        # 初始化客户端 (默认使用本地持久化模式)
        try:
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_DB_PATH
            )
            # 预创建两个核心集合
            self.reviews_collection = self.client.get_or_create_collection(name="customer_reviews")
            self.reports_collection = self.client.get_or_create_collection(name="decision_reports")
            self._connected = True
        except Exception as e:
            print(f"[Chroma] Init warning: {e}. Using mock mode.")
            self._connected = False

    def add_reviews(self, product_id: str, reviews: List[str], metadatas: Optional[List[Dict]] = None):
        """
        写入评论/舆情文本
        :param product_id: 商品ID (作为 metadata)
        :param reviews: 评论文本列表
        :param metadatas: 额外的元数据列表
        """
        if not self._connected or not reviews: return

        # 生成唯一 ID
        ids = [f"review_{product_id}_{i}" for i in range(len(reviews))]
        
        # 构造元数据
        if metadatas is None:
            metadatas = [{"product_id": product_id, "type": "review"} for _ in reviews]
        
        self.reviews_collection.add(
            documents=reviews,
            metadatas=metadatas,
            ids=ids
        )

    def search_similar_reviews(self, query: str, n_results: int = 5) -> List[str]:
        """
        检索相似评论
        :param query: 查询语句 (如 "电池续航差")
        :param n_results: 返回条数
        :return: 相似评论文本列表
        """
        if not self._connected: return []

        results = self.reviews_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Chroma 返回的是列表的列表，取第一个 query 的结果
        if results and results['documents']:
            return results['documents'][0]
        return []

    def add_decision_report(self, product_id: str, report_text: str, decision_result: str):
        """
        写入历史决策报告
        :param product_id: 商品ID
        :param report_text: 报告全文
        :param decision_result: 决策结论 (如 "打折", "维持")
        """
        if not self._connected: return

        import uuid
        doc_id = f"report_{product_id}_{uuid.uuid4()}"
        
        self.reports_collection.add(
            documents=[report_text],
            metadatas=[{"product_id": product_id, "result": decision_result, "type": "report"}],
            ids=[doc_id]
        )

    def search_similar_reports(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        检索历史相似报告 (用于 RAG)
        :param query: 查询语句 (如 "库存积压且销量下滑")
        :return: 包含 report_text 和 decision_result 的字典列表
        """
        if not self._connected: return []

        results = self.reports_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        output = []
        if results and results['documents']:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            for doc, meta in zip(docs, metas):
                output.append({
                    "report_text": doc,
                    "decision_result": meta.get("result", "unknown")
                })
        return output

# 单例导出
chroma_client = ChromaClient()
