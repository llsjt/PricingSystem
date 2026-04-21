"""通用 Schema 模块，存放多个业务对象复用的基础字段定义。"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
