from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.models.entities import User, Wallet
from src.schemas.common import AuthResponse, MeResponse, TelegramAuthIn, UserOut
from src.services.services import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=AuthResponse)
async def telegram_auth(payload: TelegramAuthIn, request: Request, db: AsyncSession = Depends(get_db)):
    token, user = await AuthService(db).telegram_login(payload, request)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wallet = await db.get(Wallet, current_user.id)
    return MeResponse(user=UserOut.model_validate(current_user), balance=wallet.balance if wallet else 0)
