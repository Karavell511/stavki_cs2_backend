import uuid

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_redis
from src.db.session import get_db
from src.models.entities import User
from src.schemas.common import BetCreate, BetOut
from src.services.services import BettingService, enforce_whitelisted

router = APIRouter(prefix="/bets", tags=["bets"])


@router.post("", response_model=BetOut)
async def place_bet(
    payload: BetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
):
    await enforce_whitelisted(db, request, user, "/bets")
    bet = await BettingService(db, redis).place_bet(user, payload.stream_id, payload.team_id, payload.amount)
    return BetOut.model_validate(bet)


@router.get("/me", response_model=list[BetOut])
async def my_bets(
    request: Request,
    stream_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await enforce_whitelisted(db, request, user, "/bets/me")
    from sqlalchemy import select
    from src.models.entities import Bet

    stmt = select(Bet).where(Bet.user_id == user.id)
    if stream_id:
        stmt = stmt.where(Bet.stream_id == stream_id)
    bets = list(await db.scalars(stmt.order_by(Bet.created_at.desc())))
    return [BetOut.model_validate(b) for b in bets]
