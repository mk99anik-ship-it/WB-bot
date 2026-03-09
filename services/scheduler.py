import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal
from core.models import TrackedItem, PriceHistory, User
from services.wb_parser import fetch_product, PLATFORM_WB
from services.notifier import notify_price_drop, notify_admin
from core.config import config

logger = logging.getLogger(__name__)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


async def check_prices(bot) -> None:
    """Проверяет цены для всех отслеживаемых товаров."""
    logger.debug("Запуск проверки цен...")
    now = datetime.utcnow()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrackedItem).options(selectinload(TrackedItem.user))
        )
        items = result.scalars().all()

    checked = 0
    notified = 0

    for item in items:
        user = item.user
        # Определяем интервал проверки для пользователя
        interval_minutes = (
            config.PAID_CHECK_INTERVAL if user.is_subscribed else config.FREE_CHECK_INTERVAL
        )
        # Проверяем последнюю запись в истории
        async with AsyncSessionLocal() as session:
            last_history = await session.execute(
                select(PriceHistory)
                .where(PriceHistory.item_id == item.id)
                .order_by(PriceHistory.checked_at.desc())
                .limit(1)
            )
            last = last_history.scalar_one_or_none()

        if last:
            elapsed = (now - last.checked_at).total_seconds() / 60
            if elapsed < interval_minutes:
                continue  # Ещё не время проверять

        product = await fetch_product(item.article, item.platform or PLATFORM_WB)
        if product is None:
            logger.warning(f"Не удалось получить данные для артикула {item.article}")
            continue

        checked += 1
        new_price = product.price
        old_price = item.last_price

        async with AsyncSessionLocal() as session:
            # Сохраняем в историю
            history_entry = PriceHistory(item_id=item.id, price=new_price, checked_at=now)
            session.add(history_entry)

            # Обновляем last_price и name
            db_item = await session.get(TrackedItem, item.id)
            db_item.last_price = new_price
            db_item.name = product.name
            await session.commit()

        # Уведомление если цена упала
        if old_price and new_price < old_price:
            should_notify = item.notify_any_drop
            if item.target_price and new_price <= item.target_price:
                should_notify = True

            if should_notify:
                await notify_price_drop(
                    bot=bot,
                    telegram_id=user.telegram_id,
                    item_name=product.name,
                    article=item.article,
                    old_price=old_price,
                    new_price=new_price,
                    target_price=item.target_price,
                    url=product.url,
                )
                notified += 1

    if notified > 0:
        logger.info(f"Проверка цен: проверено {checked}, уведомлений {notified}")


def create_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Запускать каждые 10 минут — внутри сама логика решает, кого проверять
    scheduler.add_job(check_prices, "interval", minutes=10, args=[bot])
    # Дайджест: проверяем каждую минуту у кого сейчас время рассылки
    scheduler.add_job(send_digests, "interval", minutes=1, args=[bot])
    return scheduler


# ──────────────────────────── ДАЙДЖЕСТ ────────────────────────────

async def send_digests(bot) -> None:
    """Отправляет ежедневный дайджест пользователям у которых сейчас время рассылки."""
    now_moscow = datetime.now(MOSCOW_TZ)
    hour, minute = now_moscow.hour, now_moscow.minute

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.digest_hour == hour, User.digest_minute == minute)
            .options(selectinload(User.items))
        )
        users = result.scalars().all()

    for user in users:
        try:
            await _send_user_digest(bot, user, now_moscow)
        except Exception as e:
            logger.error(f"Ошибка дайджеста для {user.telegram_id}: {e}")


async def _send_user_digest(bot, user: User, now_moscow: datetime) -> None:
    from aiogram.exceptions import TelegramForbiddenError

    if not user.items:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "☀️ Доброе утро! У тебя пока нет отслеживаемых товаров.\n\n"
                    "Добавь первый: /add"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    since_24h = now_moscow.astimezone(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    dropped = []
    unchanged_count = 0
    total_now = 0.0
    total_prev = 0.0

    for item in user.items:
        if item.last_price is None:
            continue

        current_price = item.last_price
        total_now += current_price

        # Ищем цену ~24 часа назад
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PriceHistory)
                .where(
                    PriceHistory.item_id == item.id,
                    PriceHistory.checked_at <= since_24h,
                )
                .order_by(PriceHistory.checked_at.desc())
                .limit(1)
            )
            old_record = result.scalar_one_or_none()

        old_price = old_record.price if old_record else current_price
        total_prev += old_price

        if old_record and current_price < old_price:
            drop_rub = old_price - current_price
            drop_pct = round(drop_rub / old_price * 100, 1)
            dropped.append({
                "name": item.name,
                "article": item.article,
                "old": old_price,
                "new": current_price,
                "drop_rub": drop_rub,
                "drop_pct": drop_pct,
                "target_hit": bool(item.target_price and current_price <= item.target_price),
            })
        else:
            unchanged_count += 1

    # Формируем сообщение
    lines = ["☀️ <b>Доброе утро! Вот что изменилось за ночь:</b>\n"]

    if dropped:
        lines.append(f"🔻 <b>Подешевело ({len(dropped)} {_items_word(len(dropped))}):</b>")
        for d in dropped:
            url = f"https://www.wildberries.ru/catalog/{d['article']}/detail.aspx"
            name = d["name"][:45] + ("…" if len(d["name"]) > 45 else "")
            line = (
                f"  • <a href='{url}'>{name}</a>: "
                f"<s>{d['old']:.0f} ₽</s> → <b>{d['new']:.0f} ₽</b> "
                f"(−{d['drop_rub']:.0f} ₽, −{d['drop_pct']}%)"
            )
            if d["target_hit"]:
                line += " 🎯 <b>цель достигнута!</b>"
            lines.append(line)
        lines.append("")

    if unchanged_count:
        lines.append(f"➡️ Без изменений: {unchanged_count} {_items_word(unchanged_count)}\n")

    lines.append(f"💰 Вишлист сейчас: <b>{total_now:.0f} ₽</b>")
    if total_prev != total_now and total_prev > 0:
        diff = total_prev - total_now
        lines.append(f"   (вчера было {total_prev:.0f} ₽, экономия за ночь: <b>{diff:.0f} ₽</b>)")

    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text="\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except TelegramForbiddenError:
        pass


def _items_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "товаров"
    r = n % 10
    if r == 1:
        return "товар"
    if 2 <= r <= 4:
        return "товара"
    return "товаров"
