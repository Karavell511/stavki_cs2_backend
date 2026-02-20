import math
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import create_access_token, verify_telegram_payload
from src.models.entities import (
    Bet,
    BetStatus,
    ChatMessage,
    LoginLog,
    Stream,
    StreamStatus,
    Team,
    Transaction,
    TransactionType,
    UnauthorizedAttempt,
    User,
    UserRole,
    Wallet,
)
from src.schemas.common import TelegramAuthIn
from src.services.rate_limit import RateLimiter


async def log_unauthorized(db: AsyncSession, request: Request, endpoint: str, reason: str, telegram_id: int | None = None, username: str | None = None) -> None:
    attempt = UnauthorizedAttempt(
        telegram_id=telegram_id,
        username=username,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        endpoint=endpoint,
        reason=reason,
    )
    db.add(attempt)
    await db.commit()


async def enforce_whitelisted(db: AsyncSession, request: Request, user: User, endpoint: str) -> None:
    if user.is_banned:
        await log_unauthorized(db, request, endpoint, "banned", user.telegram_id, user.username)
        raise HTTPException(status_code=403, detail="Banned")
    if not user.is_whitelisted and user.role != UserRole.ADMIN:
        await log_unauthorized(db, request, endpoint, "not_whitelisted", user.telegram_id, user.username)
        raise HTTPException(status_code=403, detail="Not whitelisted")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def telegram_login(self, payload: TelegramAuthIn, request: Request) -> tuple[str, User]:
        data = payload.model_dump()
        if not verify_telegram_payload(data):
            await log_unauthorized(self.db, request, "/auth/telegram", "telegram_hash_invalid", payload.id, payload.username)
            raise HTTPException(status_code=401, detail="Invalid Telegram payload")

        user = await self.db.scalar(select(User).where(User.telegram_id == payload.id))
        settings = get_settings()
        if not user:
            is_admin = payload.id in settings.parsed_admin_ids
            user = User(
                telegram_id=payload.id,
                username=payload.username,
                first_name=payload.first_name,
                last_name=payload.last_name,
                photo_url=payload.photo_url,
                role=UserRole.ADMIN if is_admin else UserRole.USER,
                is_whitelisted=is_admin,
                is_banned=False,
            )
            self.db.add(user)
            await self.db.flush()
            self.db.add(Wallet(user_id=user.id, balance=1000))
        else:
            user.username = payload.username
            user.first_name = payload.first_name
            user.last_name = payload.last_name
            user.photo_url = payload.photo_url

        if user.is_banned:
            await self.db.commit()
            await log_unauthorized(self.db, request, "/auth/telegram", "banned_login", user.telegram_id, user.username)
            raise HTTPException(status_code=403, detail="Banned")
        if not user.is_whitelisted and user.role != UserRole.ADMIN:
            await self.db.commit()
            await log_unauthorized(self.db, request, "/auth/telegram", "not_whitelisted_login", user.telegram_id, user.username)
            raise HTTPException(status_code=403, detail="Not whitelisted")

        self.db.add(LoginLog(user_id=user.id, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent")))
        await self.db.commit()
        await self.db.refresh(user)
        return create_access_token(str(user.id)), user


class BettingService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.limiter = RateLimiter(redis)

    async def place_bet(self, user: User, stream_id: uuid.UUID, team_id: uuid.UUID, amount: int) -> Bet:
        allowed = await self.limiter.hit(f"bet:{user.id}", limit=5, window_seconds=60)
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        async with self.db.begin():
            stream = await self.db.get(Stream, stream_id)
            if not stream:
                raise HTTPException(status_code=404, detail="Stream not found")
            lock_time = min(stream.betting_locked_at, stream.start_time)
            if datetime.now(UTC) >= lock_time:
                raise HTTPException(status_code=400, detail="Betting locked")

            team = await self.db.get(Team, team_id)
            if not team or team.stream_id != stream_id:
                raise HTTPException(status_code=400, detail="Invalid team")

            existing = await self.db.scalar(select(Bet).where(Bet.user_id == user.id, Bet.stream_id == stream_id).with_for_update())
            if existing:
                raise HTTPException(status_code=400, detail="One bet per stream allowed")

            wallet = await self.db.scalar(select(Wallet).where(Wallet.user_id == user.id).with_for_update())
            if not wallet or wallet.balance < amount:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            wallet.balance -= amount
            bet = Bet(user_id=user.id, stream_id=stream_id, team_id=team_id, amount=amount, status=BetStatus.ACTIVE)
            self.db.add(bet)
            self.db.add(Transaction(user_id=user.id, type=TransactionType.BET, amount=-amount, stream_id=stream_id, reason="User bet placement"))

        await self.db.refresh(bet)
        return bet

    async def settle_stream(self, stream_id: uuid.UUID, winner_team_id: uuid.UUID) -> None:
        async with self.db.begin():
            stream = await self.db.get(Stream, stream_id)
            if not stream:
                raise HTTPException(status_code=404, detail="Stream not found")

            active_bets = list(
                await self.db.scalars(select(Bet).where(Bet.stream_id == stream_id, Bet.status == BetStatus.ACTIVE).with_for_update())
            )
            total_pool = sum(b.amount for b in active_bets)
            winners = [b for b in active_bets if b.team_id == winner_team_id]
            winners_pool = sum(b.amount for b in winners)
            losers_pool = total_pool - winners_pool

            if winners_pool == 0:
                for bet in active_bets:
                    bet.status = BetStatus.REFUNDED
                    wallet = await self.db.scalar(select(Wallet).where(Wallet.user_id == bet.user_id).with_for_update())
                    if wallet:
                        wallet.balance += bet.amount
                    self.db.add(Transaction(user_id=bet.user_id, type=TransactionType.REFUND, amount=bet.amount, stream_id=stream_id, reason="No winners"))
            else:
                for bet in active_bets:
                    if bet.team_id == winner_team_id:
                        gain = math.floor(losers_pool * (bet.amount / winners_pool))
                        payout = bet.amount + gain
                        bet.status = BetStatus.WON
                        wallet = await self.db.scalar(select(Wallet).where(Wallet.user_id == bet.user_id).with_for_update())
                        if wallet:
                            wallet.balance += payout
                        self.db.add(Transaction(user_id=bet.user_id, type=TransactionType.WIN, amount=payout, stream_id=stream_id, reason="Winner payout"))
                    else:
                        bet.status = BetStatus.LOST

            stream.status = StreamStatus.FINISHED
            stream.betting_locked_at = datetime.now(UTC)


class ChatService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.limiter = RateLimiter(redis)

    async def create_message(self, stream_id: uuid.UUID, user_id: uuid.UUID, message: str) -> ChatMessage:
        allowed = await self.limiter.hit(f"chat:{user_id}", limit=20, window_seconds=60)
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        msg = ChatMessage(stream_id=stream_id, user_id=user_id, message=message)
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg
