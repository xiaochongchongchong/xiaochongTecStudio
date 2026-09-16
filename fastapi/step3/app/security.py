from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings

ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """登录成功后，用 SECRET_KEY 签发一个 JWT"""
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """验证 token：签名是否有效 + 是否过期。失效则抛 jwt.InvalidTokenError"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
