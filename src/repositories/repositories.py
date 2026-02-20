import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entities import (
    Bet,
    BetStatus,
    ChatMessage,
    LoginLog,
    Stream,
    Team,
    Transaction,
    UnauthorizedAttempt,
    User,
    Wallet,
)


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.db.scalar(select(User).where(User.telegram_id == telegram_id))

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def list_users(self) -> list[User]:
        rows = await self.db.scalars(select(User).order_by(User.created_at.desc()))
        return list(rows)


class StreamRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_streams(self) -> list[Stream]:
        rows = await self.db.scalars(select(Stream).order_by(Stream.start_time.desc()))
        return list(rows)

    async def get_stream(self, stream_id: uuid.UUID) -> Stream | None:
        return await self.db.get(Stream, stream_id)

    async def get_teams(self, stream_id: uuid.UUID) -> list[Team]:
        rows = await self.db.scalars(select(Team).where(Team.stream_id == stream_id))
        return list(rows)


class BetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_stream_bet(self, user_id: uuid.UUID, stream_id: uuid.UUID) -> Bet | None:
        return await self.db.scalar(select(Bet).where(Bet.user_id == user_id, Bet.stream_id == stream_id))

    async def list_stream_bets(self, stream_id: uuid.UUID) -> list[Bet]:
        rows = await self.db.scalars(select(Bet).where(Bet.stream_id == stream_id))
        return list(rows)

    async def list_user_bets(self, user_id: uuid.UUID, stream_id: uuid.UUID | None = None) -> list[Bet]:
        stmt: Select[tuple[Bet]] = select(Bet).where(Bet.user_id == user_id)
        if stream_id:
            stmt = stmt.where(Bet.stream_id == stream_id)
        rows = await self.db.scalars(stmt.order_by(Bet.created_at.desc()))
        return list(rows)


class SecurityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_attempts(self, telegram_id: int | None = None, since: datetime | None = None) -> list[UnauthorizedAttempt]:
        stmt: Select[tuple[UnauthorizedAttempt]] = select(UnauthorizedAttempt)
        if telegram_id is not None:
            stmt = stmt.where(UnauthorizedAttempt.telegram_id == telegram_id)
        if since is not None:
            stmt = stmt.where(UnauthorizedAttempt.created_at >= since)
        rows = await self.db.scalars(stmt.order_by(UnauthorizedAttempt.created_at.desc()))
        return list(rows)

    async def list_logins(self) -> list[LoginLog]:
        rows = await self.db.scalars(select(LoginLog).order_by(LoginLog.created_at.desc()))
        return list(rows)


class WalletRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_wallet_for_update(self, user_id: uuid.UUID) -> Wallet | None:
        stmt = select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        return await self.db.scalar(stmt)


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_message(self, stream_id: uuid.UUID, user_id: uuid.UUID, message: str) -> ChatMessage:
        msg = ChatMessage(stream_id=stream_id, user_id=user_id, message=message)
        self.db.add(msg)
        await self.db.flush()
        return msg
