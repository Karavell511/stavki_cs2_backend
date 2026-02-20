import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import bearer_scheme, decode_token, extract_bearer_token
from src.db.session import get_db
from src.models.entities import User, UserRole, Wallet


async def get_redis() -> AsyncGenerator[Redis, None]:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()


async def get_current_user(db: AsyncSession = Depends(get_db), credentials=Depends(bearer_scheme)) -> User:
    token = extract_bearer_token(credentials)
    payload = decode_token(token)
    sub = payload.get("sub")
    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


async def get_current_balance(user: User, db: AsyncSession) -> int:
    wallet = await db.get(Wallet, user.id)
    return wallet.balance if wallet else 0
