import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.models.entities import BetStatus, StreamStatus, StreamType, TransactionType, UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    telegram_id: int
    username: str | None
    first_name: str
    last_name: str | None
    photo_url: str | None
    role: UserRole
    is_whitelisted: bool
    is_banned: bool


class TeamCreate(BaseModel):
    name: str
    logo_url: str | None = None
    color: str | None = None


class TeamOut(TeamCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    stream_id: uuid.UUID


class StreamCreate(BaseModel):
    title: str
    description: str | None = None
    stream_type: StreamType
    stream_url: str
    status: StreamStatus = StreamStatus.SCHEDULED
    start_time: datetime
    betting_locked_at: datetime
    teams: list[TeamCreate]


class StreamUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    stream_type: StreamType | None = None
    stream_url: str | None = None
    status: StreamStatus | None = None
    start_time: datetime | None = None
    betting_locked_at: datetime | None = None


class StreamStatusIn(BaseModel):
    status: StreamStatus


class StreamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    description: str | None
    stream_type: StreamType
    stream_url: str
    status: StreamStatus
    start_time: datetime
    betting_locked_at: datetime
    created_by: uuid.UUID | None
    created_at: datetime
    teams: list[TeamOut]


class TelegramAuthIn(BaseModel):
    id: int
    username: str | None = None
    first_name: str
    last_name: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
    balance: int


class BetCreate(BaseModel):
    stream_id: uuid.UUID
    team_id: uuid.UUID
    amount: int


class BetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    stream_id: uuid.UUID
    team_id: uuid.UUID
    amount: int
    status: BetStatus
    created_at: datetime


class BalanceAdjustIn(BaseModel):
    amount: int
    reason: str | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    type: TransactionType
    amount: int
    stream_id: uuid.UUID | None
    reason: str | None
    created_at: datetime


class AdminUserCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str = "Pending"
    last_name: str | None = None


class AdminUserPatch(BaseModel):
    role: UserRole | None = None
    is_whitelisted: bool | None = None
    is_banned: bool | None = None


class SetWinnerIn(BaseModel):
    team_id: uuid.UUID


class StreamStatsOut(BaseModel):
    total_amount: int
    per_team_amount: dict[str, int]
    per_team_percent: dict[str, float]
    bettors_count: int
    top_bets: list[dict[str, Any]]


class UnauthorizedAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    telegram_id: int | None
    username: str | None
    ip: str | None
    user_agent: str | None
    endpoint: str
    reason: str
    created_at: datetime


class LoginLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    ip: str | None
    user_agent: str | None
    created_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    stream_id: uuid.UUID
    user_id: uuid.UUID
    message: str
    is_deleted: bool
    created_at: datetime
