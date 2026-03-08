from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from core.config import config
from core.database import AsyncSessionLocal
from core.models import User

router = Router()


def _is_admin(message: Message) -> bool:
    return message.from_user.id == config.ADMIN_ID


# /grant <telegram_id> [дней]
@router.message(Command("grant"))
async def cmd_grant(message: Message) -> None:
    if not _is_admin(message):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer(
            "ℹ️ Использование: <code>/grant &lt;telegram_id&gt; [дней]</code>\n"
            "Пример: <code>/grant 123456789 30</code>\n"
            "По умолчанию 30 дней.",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный Telegram ID — должно быть число.", parse_mode="HTML")
        return

    days = config.SUBSCRIPTION_DAYS
    if len(parts) >= 3:
        try:
            days = int(parts[2])
            if days <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Количество дней должно быть положительным числом.", parse_mode="HTML")
            return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == target_id))
        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                f"❌ Пользователь с ID <code>{target_id}</code> не найден в базе.\n"
                "Он должен хотя бы раз написать боту.",
                parse_mode="HTML",
            )
            return

        new_end = max(
            user.subscription_end or datetime.utcnow(),
            datetime.utcnow(),
        ) + timedelta(days=days)

        user.subscription_end = new_end
        await session.commit()

    username_str = f"@{user.username}" if user.username else f"ID {target_id}"
    await message.answer(
        f"✅ Премиум выдан!\n\n"
        f"👤 Пользователь: {username_str} (<code>{target_id}</code>)\n"
        f"📅 Дней добавлено: <b>{days}</b>\n"
        f"⏳ Подписка до: <b>{new_end.strftime('%d.%m.%Y')}</b>",
        parse_mode="HTML",
    )


# /revoke <telegram_id>
@router.message(Command("revoke"))
async def cmd_revoke(message: Message) -> None:
    if not _is_admin(message):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer(
            "ℹ️ Использование: <code>/revoke &lt;telegram_id&gt;</code>\n"
            "Пример: <code>/revoke 123456789</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный Telegram ID — должно быть число.", parse_mode="HTML")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == target_id))
        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                f"❌ Пользователь с ID <code>{target_id}</code> не найден в базе.",
                parse_mode="HTML",
            )
            return

        user.subscription_end = None
        await session.commit()

    username_str = f"@{user.username}" if user.username else f"ID {target_id}"
    await message.answer(
        f"🚫 Премиум отозван у {username_str} (<code>{target_id}</code>).",
        parse_mode="HTML",
    )


# /users — список всех пользователей
@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    if not _is_admin(message):
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()

    if not users:
        await message.answer("Пользователей пока нет.", parse_mode="HTML")
        return

    now = datetime.utcnow()
    lines = [f"👥 <b>Пользователи ({len(users)}):</b>\n"]
    for u in users:
        name = f"@{u.username}" if u.username else f"ID {u.telegram_id}"
        if u.telegram_id == config.ADMIN_ID:
            status = "👑 admin"
        elif u.subscription_end and u.subscription_end > now:
            days_left = (u.subscription_end - now).days
            status = f"⭐ premium ({days_left}д)"
        else:
            status = "🆓 free"
        lines.append(f"• {name} — {status}")

    await message.answer("\n".join(lines), parse_mode="HTML")
