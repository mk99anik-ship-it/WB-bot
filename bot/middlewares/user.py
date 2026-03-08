from datetime import datetime
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.models import User


class UserMiddleware(BaseMiddleware):
    """Автоматически создаёт пользователя в БД при первом обращении."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == tg_user.id)
                )
                user = result.scalar_one_or_none()
                is_new = user is None
                if is_new:
                    user = User(
                        telegram_id=tg_user.id,
                        username=tg_user.username,
                        created_at=datetime.utcnow(),
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                data["db_user"] = user
                data["is_new_user"] = is_new

        return await handler(event, data)
