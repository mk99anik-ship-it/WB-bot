from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.keyboards.inline import digest_menu_kb
from core.database import AsyncSessionLocal
from core.models import User

router = Router()


def _digest_text(db_user: User) -> str:
    if db_user.digest_hour is not None:
        return (
            f"☀️ <b>Ежедневный дайджест</b>\n\n"
            f"Статус: <b>включён</b> в {db_user.digest_hour:02d}:{db_user.digest_minute:02d} по Москве\n\n"
            "Каждый день в указанное время я пришлю сводку:\n"
            "что подешевело, что достигло цели, итого по вишлисту.\n\n"
            "Нажми на время чтобы изменить, или выключи:"
        )
    return (
        "☀️ <b>Ежедневный дайджест</b>\n\n"
        "Статус: <b>выключен</b>\n\n"
        "Выбери удобное время — каждый день буду присылать сводку:\n"
        "что подешевело, что достигло цели, итого по вишлисту."
    )


# ── Открытие меню через кнопку или команду ──

@router.callback_query(F.data == "digest_menu")
async def cb_digest_menu(callback: CallbackQuery, db_user: User) -> None:
    await callback.message.edit_text(
        _digest_text(db_user),
        parse_mode="HTML",
        reply_markup=digest_menu_kb(db_user.digest_hour, db_user.digest_minute),
    )
    await callback.answer()


@router.message(Command("digest"))
async def cmd_digest(message: Message, db_user: User) -> None:
    await message.answer(
        _digest_text(db_user),
        parse_mode="HTML",
        reply_markup=digest_menu_kb(db_user.digest_hour, db_user.digest_minute),
    )


# ── Выбор времени из пресетов ──

@router.callback_query(F.data.startswith("digest_set:"))
async def cb_digest_set(callback: CallbackQuery, db_user: User) -> None:
    _, h, m = callback.data.split(":")
    hour, minute = int(h), int(m)

    async with AsyncSessionLocal() as session:
        user = await session.get(User, db_user.id)
        user.digest_hour = hour
        user.digest_minute = minute
        await session.commit()

    # Обновляем db_user в памяти чтобы правильно отрисовать клавиатуру
    db_user.digest_hour = hour
    db_user.digest_minute = minute

    await callback.message.edit_text(
        _digest_text(db_user),
        parse_mode="HTML",
        reply_markup=digest_menu_kb(hour, minute),
    )
    await callback.answer(f"✅ Дайджест включён в {hour:02d}:{minute:02d}")


# ── Выключить дайджест ──

@router.callback_query(F.data == "digest_off")
async def cb_digest_off(callback: CallbackQuery, db_user: User) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, db_user.id)
        user.digest_hour = None
        user.digest_minute = None
        await session.commit()

    db_user.digest_hour = None
    db_user.digest_minute = None

    await callback.message.edit_text(
        _digest_text(db_user),
        parse_mode="HTML",
        reply_markup=digest_menu_kb(None, None),
    )
    await callback.answer("🔕 Дайджест выключен")


# ── Заглушка для декоративных кнопок-заголовков ──

@router.callback_query(F.data == "digest_noop")
async def cb_digest_noop(callback: CallbackQuery) -> None:
    await callback.answer()
