from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """
    统一 API 响应封装
    {
        "success": true,
        "message": "success",
        "code": 200,
        "data": { ... }
    }
    """
    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(default="success", description="提示信息")
    code: int = Field(default=200, description="业务状态码 (200=成功, 其他=异常)")
    data: Optional[T] = Field(default=None, description="业务数据载体")

    @classmethod
    def success_resp(cls, data: T, message: str = "success"):
        return cls(success=True, code=200, message=message, data=data)

    @classmethod
    def error_resp(cls, message: str, code: int = 500):
        return cls(success=False, code=code, message=message, data=None)
