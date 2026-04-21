"""内部安全模块，负责校验 Java 调用 Python 内部接口时使用的访问令牌。"""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def _should_bypass_internal_token() -> bool:
    settings = get_settings()
    return (not settings.is_production) and settings.allow_dev_internal_token_bypass and not settings.internal_api_token.strip()


def internal_token_is_valid(token: str | None) -> bool:
    settings = get_settings()
    expected = settings.internal_api_token.strip()
    if not expected:
        return _should_bypass_internal_token()
    return token == expected


def verify_internal_token(x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> None:
    if internal_token_is_valid(x_internal_token):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")
