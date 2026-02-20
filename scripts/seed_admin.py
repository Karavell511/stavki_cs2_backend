import asyncio

from sqlalchemy import select

from src.core.config import get_settings
from src.db.session import AsyncSessionLocal
from src.models.entities import User, UserRole, Wallet


async def main() -> None:
    settings = get_settings()
    admin_ids = settings.parsed_admin_ids
    if not admin_ids:
        print("No TELEGRAM_ADMIN_IDS configured")
        return

    async with AsyncSessionLocal() as db:
        for tg_id in admin_ids:
            user = await db.scalar(select(User).where(User.telegram_id == tg_id))
            if not user:
                user = User(
                    telegram_id=tg_id,
                    username=f"admin_{tg_id}",
                    first_name="Admin",
                    role=UserRole.ADMIN,
                    is_whitelisted=True,
                    is_banned=False,
                )
                db.add(user)
                await db.flush()
                db.add(Wallet(user_id=user.id, balance=10000))
            else:
                user.role = UserRole.ADMIN
                user.is_whitelisted = True
                if not await db.get(Wallet, user.id):
                    db.add(Wallet(user_id=user.id, balance=10000))
        await db.commit()
    print("Seed complete")


if __name__ == "__main__":
    asyncio.run(main())
