import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.models.entities import Stream, Team, User
from src.schemas.common import StreamOut, TeamOut
from src.services.services import enforce_whitelisted

router = APIRouter(prefix="/streams", tags=["streams"])


async def _to_stream_out(db: AsyncSession, stream: Stream) -> StreamOut:
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


@router.get("", response_model=list[StreamOut])
async def list_streams(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await enforce_whitelisted(db, request, user, "/streams")
    streams = list(await db.scalars(select(Stream).order_by(Stream.start_time.desc())))
    return [await _to_stream_out(db, s) for s in streams]


@router.get("/{stream_id}", response_model=StreamOut)
async def get_stream(stream_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await enforce_whitelisted(db, request, user, "/streams/{id}")
    stream = await db.get(Stream, stream_id)
    if not stream:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Stream not found")
    return await _to_stream_out(db, stream)
