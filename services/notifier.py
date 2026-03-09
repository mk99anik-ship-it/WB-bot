from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError


async def notify_price_drop(
    bot: Bot,
    telegram_id: int,
    item_name: str,
    article: str,
    old_price: float,
    new_price: float,
    target_price: float | None,
    url: str | None = None,
) -> None:
    drop_pct = round((old_price - new_price) / old_price * 100, 1)
    if not url:
        url = f"https://www.wildberries.ru/catalog/{article}/detail.aspx"

    text = (
        f"🔔 <b>Снижение цены!</b>\n\n"
        f"📦 <a href='{url}'>{item_name}</a>\n\n"
        f"💰 Было: <s>{old_price:.0f} ₽</s>\n"
        f"✅ Стало: <b>{new_price:.0f} ₽</b>\n"
        f"📉 Скидка: <b>−{drop_pct}%</b>"
    )

    if target_price and new_price <= target_price:
        text += f"\n\n🎯 <b>Достигнута целевая цена: {target_price:.0f} ₽!</b>"

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except TelegramForbiddenError:
        # Пользователь заблокировал бота — ничего не делаем
        pass


async def notify_admin(bot: Bot, admin_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
    except Exception:
        pass
