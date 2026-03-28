from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_internal_token(x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> None:
    settings = get_settings()
    token = settings.internal_api_token.strip()
    if not token:
        return
    if x_internal_token != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")

