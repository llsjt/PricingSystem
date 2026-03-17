class BaseAgentSystemException(Exception):
    """项目所有自定义异常的基类"""
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)

class AgentExecutionException(BaseAgentSystemException):
    """
    Agent 执行过程中发生的异常
    (如：LLM 调用失败、Prompt 解析错误)
    """
    def __init__(self, message: str = "Agent execution failed"):
        super().__init__(message, code=500)

class InvalidDecisionInputException(BaseAgentSystemException):
    """
    输入数据不合法异常
    (如：价格为负、库存数据缺失)
    """
    def __init__(self, message: str = "Invalid input data for decision"):
        super().__init__(message, code=400)

class RiskControlException(BaseAgentSystemException):
    """
    风控严重违规异常
    (如：检测到欺诈风险，强制中断)
    """
    def __init__(self, message: str = "Risk control violation detected"):
        super().__init__(message, code=403)

class ExternalDependencyException(BaseAgentSystemException):
    """
    外部依赖服务异常
    (如：Redis 连接失败、Chroma 服务不可用)
    """
    def __init__(self, message: str = "External dependency service unavailable"):
        super().__init__(message, code=503)
