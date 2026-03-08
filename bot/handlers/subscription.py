from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

from bot.keyboards.inline import subscription_kb, main_menu_kb
from core.config import config
from core.database import AsyncSessionLocal
from core.models import User

router = Router()

SUB_PAYLOAD = "wb_monitor_subscription"


def subscription_info_text(user: User) -> str:
    if user.is_subscribed:
        if user.is_admin or user.subscription_end is None:
            end_str = "∞ (навсегда)"
            extend_hint = ""
        else:
            end_str = user.subscription_end.strftime("%d.%m.%Y")
            extend_hint = (
                f"\n\n🔄 Хочешь продлить? Нажми кнопку ниже — "
                f"+{config.SUBSCRIPTION_DAYS} дней за {config.SUBSCRIPTION_PRICE_STARS} Stars "
                f"(добавятся к текущей дате)"
            )
        return (
            f"⭐ <b>Подписка активна</b> до <b>{end_str}</b>\n\n"
            f"Твои возможности:\n"
            f"• До {config.PAID_ITEMS_LIMIT} товаров\n"
            f"• Проверка каждые {config.PAID_CHECK_INTERVAL} мин"
            f"{extend_hint}"
        )
    return (
        f"⭐ <b>Оформи подписку</b>\n\n"
        f"Стоимость: <b>{config.SUBSCRIPTION_PRICE_STARS} Telegram Stars</b> / {config.SUBSCRIPTION_DAYS} дней\n\n"
        f"<b>Что даёт подписка:</b>\n"
        f"• До {config.PAID_ITEMS_LIMIT} товаров (сейчас: {config.FREE_ITEMS_LIMIT})\n"
        f"• Проверка каждые {config.PAID_CHECK_INTERVAL} мин (сейчас: {config.FREE_CHECK_INTERVAL} мин)\n"
        f"• Приоритетная поддержка"
    )


@router.message(Command("sub"))
@router.callback_query(lambda c: c.data == "subscription")
async def show_subscription(event: Message | CallbackQuery, db_user: User) -> None:
    text = subscription_info_text(db_user)
    kb = subscription_kb(db_user.is_subscribed)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(lambda c: c.data == "pay_subscription")
async def send_invoice(callback: CallbackQuery) -> None:
    await callback.message.answer_invoice(
        title="⭐ Подписка WB Monitor",
        description=(
            f"Подписка на {config.SUBSCRIPTION_DAYS} дней: "
            f"до {config.PAID_ITEMS_LIMIT} товаров, "
            f"проверка каждые {config.PAID_CHECK_INTERVAL} мин."
        ),
        payload=SUB_PAYLOAD,
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Подписка", amount=config.SUBSCRIPTION_PRICE_STARS)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(lambda m: m.successful_payment is not None)
async def successful_payment(message: Message, db_user: User) -> None:
    if message.successful_payment.invoice_payload != SUB_PAYLOAD:
        return

    new_end = max(
        db_user.subscription_end or datetime.utcnow(),
        datetime.utcnow()
    ) + timedelta(days=config.SUBSCRIPTION_DAYS)

    async with AsyncSessionLocal() as session:
        user = await session.get(User, db_user.id)
        user.subscription_end = new_end
        await session.commit()

    await message.answer(
        f"🎉 <b>Подписка оформлена!</b>\n\n"
        f"Активна до: <b>{new_end.strftime('%d.%m.%Y')}</b>\n\n"
        f"Теперь ты можешь отслеживать до <b>{config.PAID_ITEMS_LIMIT}</b> товаров "
        f"с проверкой каждые <b>{config.PAID_CHECK_INTERVAL} мин</b>!",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
