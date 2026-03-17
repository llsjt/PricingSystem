from typing import List, Dict, Any
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from app.core.config import settings
from pydantic import BaseModel, Field

class LangChainHelper:
    """
    LangChainHelper
    LangChain 在本项目中作为底层能力层，提供 Prompt 管理、结构化解析、摘要生成和检索增强等原子能力。
    它不负责业务流程编排，业务编排由 CrewAI 或 Manager Agent 负责。
    """

    def __init__(self):
        # 初始化基础 LLM
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3
        )

    def create_structured_prompt(self, template_str: str, input_variables: List[str], pydantic_object: Any) -> ChatPromptTemplate:
        """
        创建带有结构化输出指令的 Prompt 模板
        :param template_str: 基础提示词模板
        :param input_variables: 输入变量名列表
        :param pydantic_object: 用于定义输出格式的 Pydantic 模型类
        :return: ChatPromptTemplate
        """
        parser = PydanticOutputParser(pydantic_object=pydantic_object)
        
        # 将格式指令注入到 Prompt 中
        format_instructions = parser.get_format_instructions()
        
        full_template = template_str + "\n\n{format_instructions}"
        
        prompt = ChatPromptTemplate.from_template(
            template=full_template,
            partial_variables={"format_instructions": format_instructions}
        )
        return prompt

    async def summarize_reviews(self, reviews: List[str]) -> str:
        """
        [预留能力] 使用 LangChain Map-Reduce 或 Refine 链对长评论列表进行摘要
        :param reviews: 原始评论列表
        :return: 摘要文本
        """
        if not reviews:
            return "无评论数据"
            
        # 简单实现示例：如果评论少，直接拼接；如果多，则需要分块处理
        # 这里仅展示 Prompt 构建逻辑
        template = """
        You are a customer sentiment analyst.
        Please summarize the following customer reviews into a concise paragraph.
        Highlight the main pros and cons.
        
        Reviews:
        {reviews_text}
        
        Summary:
        """
        prompt = PromptTemplate(template=template, input_variables=["reviews_text"])
        chain = prompt | self.llm
        
        # 截断过长的输入以节省 Token (Mock)
        reviews_text = "\n".join(reviews)[:3000]
        
        try:
            response = await chain.ainvoke({"reviews_text": reviews_text})
            return response.content
        except Exception as e:
            return f"摘要生成失败: {str(e)}"

    async def retrieve_history_reports(self, query: str, k: int = 3) -> List[Document]:
        """
        [预留能力] 使用 LangChain Retriever 从向量库检索历史决策报告
        :param query: 查询关键词（如商品名）
        :param k: 返回条数
        :return: 相关文档列表
        """
        # TODO: 接入真实的 VectorStoreRetriever (Chroma/FAISS)
        # retriever = vector_store.as_retriever(search_kwargs={"k": k})
        # docs = await retriever.ainvoke(query)
        
        # Mock 返回
        return [
            Document(page_content="历史报告A: 该类目商品在Q3通常需要打折...", metadata={"source": "report_001"}),
            Document(page_content="历史报告B: 竞品降价时，跟随策略效果最佳...", metadata={"source": "report_002"})
        ]

    def build_chain_for_agent(self, agent_role: str, task_desc: str) -> Any:
        """
        为特定 Agent 构建专属的 LLMChain (如果 Agent 内部逻辑比较简单，不使用 CrewAI 时可用)
        """
        template = f"""
        You are a {agent_role}.
        {task_desc}
        
        User Input: {{input}}
        Answer:
        """
        prompt = PromptTemplate.from_template(template)
        return prompt | self.llm

# 单例导出
langchain_helper = LangChainHelper()
