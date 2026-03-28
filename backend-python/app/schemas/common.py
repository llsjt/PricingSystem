from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db_ok: bool

