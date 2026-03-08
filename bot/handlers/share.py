from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.models import TrackedItem, User

router = Router()


async def _build_share_text(db_user: User) -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrackedItem)
            .where(TrackedItem.user_id == db_user.id)
            .order_by(TrackedItem.created_at)
        )
        items = result.scalars().all()

    if not items:
        return None

    total = sum(i.last_price for i in items if i.last_price is not None)

    lines = ["🛍️ <b>Мой список желаний на Wildberries:</b>\n"]
    for idx, item in enumerate(items, 1):
        price_str = f"{item.last_price:,.0f} ₽" if item.last_price else "цена неизвестна"
        url = f"https://www.wildberries.ru/catalog/{item.article}/detail.aspx"
        lines.append(f"{idx}. <a href='{url}'>{item.name}</a> — {price_str}")

    lines.append("")
    if total:
        lines.append(f"💰 <b>Итого: {total:,.0f} ₽</b>")
    lines.append("\n<i>Составлено в @wbb_moneybot</i>")
    lines.append("\n💡 <i>Перешли это сообщение подруге, мужу или в любой чат.</i>")

    return "\n".join(lines)


@router.message(Command("share"))
async def cmd_share(message: Message, db_user: User) -> None:
    text = await _build_share_text(db_user)
    if not text:
        await message.answer("📭 Твой вишлист пуст. Добавь товары через /add чтобы поделиться ими.")
        return
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(lambda c: c.data == "share_wishlist")
async def cb_share(callback: CallbackQuery, db_user: User) -> None:
    text = await _build_share_text(db_user)
    if not text:
        await callback.answer("📭 Вишлист пуст — нечем делиться!", show_alert=True)
        return
    await callback.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()
