import json
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_redis
from src.core.config import get_settings
from src.core.security import decode_token
from src.db.session import AsyncSessionLocal
from src.models.entities import User
from src.services.services import ChatService

router = APIRouter(tags=["chat"])
connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)


@router.websocket("/chat/ws/{stream_id}")
async def chat_ws(websocket: WebSocket, stream_id: uuid.UUID):
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        await websocket.close(code=1008)
        return

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or user.is_banned or (not user.is_whitelisted and user.role.value != "ADMIN"):
            await websocket.close(code=1008)
            return

    connections[stream_id].add(websocket)
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data).get("message", "").strip()
            if not message:
                continue
            async with AsyncSessionLocal() as db:
                msg = await ChatService(db, redis).create_message(stream_id, user_id, message)
                payload_out = {
                    "id": str(msg.id),
                    "stream_id": str(stream_id),
                    "user_id": str(user_id),
                    "message": message,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
            for conn in list(connections[stream_id]):
                await conn.send_json(payload_out)
    except WebSocketDisconnect:
        pass
    finally:
        connections[stream_id].discard(websocket)
        await redis.close()
