import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_redis, require_admin
from src.db.session import get_db
from src.models.entities import (
    Bet,
    ChatMessage,
    LoginLog,
    Stream,
    Team,
    Transaction,
    TransactionType,
    UnauthorizedAttempt,
    User,
    UserRole,
    Wallet,
)
from src.schemas.common import (
    AdminUserCreate,
    AdminUserPatch,
    BalanceAdjustIn,
    BetOut,
    LoginLogOut,
    SetWinnerIn,
    StreamCreate,
    StreamOut,
    StreamStatsOut,
    StreamStatusIn,
    StreamUpdate,
    TeamOut,
    UnauthorizedAttemptOut,
    UserOut,
)
from src.services.services import BettingService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    users = list(await db.scalars(select(User).order_by(User.created_at.desc())))
    return [UserOut.model_validate(u) for u in users]


@router.post("/users", response_model=UserOut)
async def create_user(payload: AdminUserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    existing = await db.scalar(select(User).where(User.telegram_id == payload.telegram_id))
    if existing:
        existing.is_whitelisted = True
        await db.commit()
        await db.refresh(existing)
        return UserOut.model_validate(existing)
    user = User(
        telegram_id=payload.telegram_id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=UserRole.USER,
        is_whitelisted=True,
        is_banned=False,
    )
    db.add(user)
    await db.flush()
    db.add(Wallet(user_id=user.id, balance=0))
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def patch_user(user_id: uuid.UUID, payload: AdminUserPatch, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = True
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/unban")
async def unban_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = False
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/balance-adjust")
async def balance_adjust(user_id: uuid.UUID, payload: BalanceAdjustIn, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    async with db.begin():
        wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        wallet.balance += payload.amount
        db.add(Transaction(user_id=user_id, type=TransactionType.ADMIN_ADJUST, amount=payload.amount, reason=payload.reason))
    return {"ok": True}


@router.post("/users/{user_id}/mute")
async def mute_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    return {"ok": True, "note": "Mute entity reserved; enforce in websocket layer if needed."}


@router.post("/streams", response_model=StreamOut)
async def create_stream(payload: StreamCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    if len(payload.teams) < 2:
        raise HTTPException(status_code=400, detail="At least 2 teams required")
    stream = Stream(
        title=payload.title,
        description=payload.description,
        stream_type=payload.stream_type,
        stream_url=payload.stream_url,
        status=payload.status,
        start_time=payload.start_time,
        betting_locked_at=payload.betting_locked_at,
        created_by=admin.id,
    )
    db.add(stream)
    await db.flush()
    for t in payload.teams:
        db.add(Team(stream_id=stream.id, name=t.name, logo_url=t.logo_url, color=t.color))
    await db.commit()
    teams = list(await db.scalars(select(Team).where(Team.stream_id == stream.id)))
    return StreamOut(
        id=stream.id,
        title=stream.title,
        description=stream.description,
        stream_type=stream.stream_type,
        stream_url=stream.stream_url,
        status=stream.status,
        start_time=stream.start_time,
        betting_locked_at=stream.betting_locked_at,
        created_by=stream.created_by,
        created_at=stream.created_at,
        teams=[TeamOut.model_validate(t) for t in teams],
    )


@router.patch("/streams/{stream_id}", response_model=StreamOut)
async def update_stream(stream_id: uuid.UUID, payload: StreamUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    stream = await db.get(Stream, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(stream, field, value)
    await db.commit()
    teams = list(await db.scalars(select(Team).where(Team.stream_id == stream.id)))
    return StreamOut(
        id=stream.id,
        title=stream.title,
        description=stream.description,
        stream_type=stream.stream_type,
        stream_url=stream.stream_url,
        status=stream.status,
        start_time=stream.start_time,
        betting_locked_at=stream.betting_locked_at,
        created_by=stream.created_by,
        created_at=stream.created_at,
        teams=[TeamOut.model_validate(t) for t in teams],
    )


@router.post("/streams/{stream_id}/status")
async def set_stream_status(stream_id: uuid.UUID, payload: StreamStatusIn, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    stream = await db.get(Stream, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    stream.status = payload.status
    await db.commit()
    return {"ok": True}


@router.post("/streams/{stream_id}/lock-betting")
async def lock_betting(stream_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    stream = await db.get(Stream, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    stream.betting_locked_at = datetime.utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/streams/{stream_id}/set-winner")
async def set_winner(
    stream_id: uuid.UUID,
    payload: SetWinnerIn,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: User = Depends(require_admin),
):
    await BettingService(db, redis).settle_stream(stream_id, payload.team_id)
    return {"ok": True}


@router.get("/bets", response_model=list[BetOut])
async def admin_bets(stream_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    stmt = select(Bet)
    if stream_id:
        stmt = stmt.where(Bet.stream_id == stream_id)
    bets = list(await db.scalars(stmt.order_by(Bet.created_at.desc())))
    return [BetOut.model_validate(b) for b in bets]


@router.get("/streams/{stream_id}/stats", response_model=StreamStatsOut)
async def stream_stats(stream_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    bets = list(await db.scalars(select(Bet).where(Bet.stream_id == stream_id)))
    total = sum(b.amount for b in bets)
    per_team: dict[str, int] = {}
    teams = {t.id: t.name for t in list(await db.scalars(select(Team).where(Team.stream_id == stream_id)))}
    for b in bets:
        team_name = teams.get(b.team_id, str(b.team_id))
        per_team[team_name] = per_team.get(team_name, 0) + b.amount
    perc = {k: (v / total * 100 if total else 0) for k, v in per_team.items()}
    top = sorted(bets, key=lambda x: x.amount, reverse=True)[:5]
    return StreamStatsOut(
        total_amount=total,
        per_team_amount=per_team,
        per_team_percent=perc,
        bettors_count=len({b.user_id for b in bets}),
        top_bets=[{"bet_id": str(b.id), "user_id": str(b.user_id), "amount": b.amount} for b in top],
    )


@router.get("/security/unauthorized-attempts", response_model=list[UnauthorizedAttemptOut])
async def unauthorized_attempts(
    telegram_id: int | None = Query(default=None),
    since: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(UnauthorizedAttempt)
    if telegram_id is not None:
        stmt = stmt.where(UnauthorizedAttempt.telegram_id == telegram_id)
    if since is not None:
        stmt = stmt.where(UnauthorizedAttempt.created_at >= since)
    rows = list(await db.scalars(stmt.order_by(UnauthorizedAttempt.created_at.desc())))
    return [UnauthorizedAttemptOut.model_validate(r) for r in rows]


@router.get("/security/logins", response_model=list[LoginLogOut])
async def login_logs(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    rows = list(await db.scalars(select(LoginLog).order_by(LoginLog.created_at.desc())))
    return [LoginLogOut.model_validate(r) for r in rows]


@router.delete("/chat/messages/{message_id}")
async def delete_chat_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    msg = await db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_deleted = True
    await db.commit()
    return {"ok": True}
