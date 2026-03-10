from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.keyboards.inline import (
    items_list_kb, confirm_delete_kb, set_target_price_kb, main_menu_kb, back_to_main_kb
)
from core.config import config
from core.database import AsyncSessionLocal
from core.models import TrackedItem, User
from services.wb_parser import fetch_product, detect_platform, product_url, PLATFORM_NAME, PLATFORM_EMOJI

router = Router()


class AddItemFSM(StatesGroup):
    waiting_for_url = State()
    waiting_for_target_price = State()


class SetTargetFSM(StatesGroup):
    waiting_for_price = State()


# --- /add и кнопка «Добавить товар» ---

@router.message(Command("add"))
@router.callback_query(lambda c: c.data == "add_item")
async def start_add_item(event: Message | CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.set_state(AddItemFSM.waiting_for_url)
    text = (
        "🔗 <b>Отправь ссылку на товар или его артикул:</b>\n\n"
        "Пример ссылки:\n"
        "<code>https://www.wildberries.ru/catalog/123456789/detail.aspx</code>\n\n"
        "Или просто артикул:\n"
        "<code>123456789</code>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=back_to_main_kb())


@router.message(AddItemFSM.waiting_for_url)
async def process_item_url(message: Message, state: FSMContext, db_user: User) -> None:
    detected = detect_platform(message.text.strip())
    if not detected:
        await message.answer(
            "❌ Не удалось распознать ссылку или артикул. Попробуй ещё раз.",
            reply_markup=back_to_main_kb(),
        )
        return

    platform, article = detected

    # Проверяем лимит
    async with AsyncSessionLocal() as session:
        count_result = await session.execute(
            select(TrackedItem).where(TrackedItem.user_id == db_user.id)
        )
        existing_items = count_result.scalars().all()
        limit = config.PAID_ITEMS_LIMIT if db_user.is_subscribed else config.FREE_ITEMS_LIMIT

        if not db_user.is_admin and len(existing_items) >= limit:
            await message.answer(
                f"⚠️ Достигнут лимит товаров ({limit}).\n"
                + ("Оформи подписку ⭐, чтобы отслеживать до 20 товаров!" if not db_user.is_subscribed else ""),
                reply_markup=main_menu_kb(),
                parse_mode="HTML",
            )
            await state.clear()
            return

        # Проверяем дубликат
        dup = next((i for i in existing_items if i.article == article), None)
        if dup:
            await message.answer(
                f"ℹ️ Этот товар уже отслеживается.",
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
            await state.clear()
            return

    emoji = PLATFORM_EMOJI.get(platform, "")
    pname = PLATFORM_NAME.get(platform, platform)
    await message.answer(f"⏳ Загружаю товар с {emoji} {pname}...")

    product = await fetch_product(article, platform)
    if product is None:
        await message.answer(
            f"❌ Не удалось получить данные о товаре.\n"
            f"Проверь ссылку и попробуй снова.",
            reply_markup=back_to_main_kb(),
        )
        return

    await state.update_data(
        article=article, platform=platform,
        name=product.name, price=product.price, url=product.url,
    )
    await state.set_state(AddItemFSM.waiting_for_target_price)

    await message.answer(
        f"✅ Найден товар {emoji}:\n\n"
        f"📦 <b>{product.name}</b>\n"
        f"💰 Цена: <b>{product.price:.0f} ₽</b>\n\n"
        f"🎯 Установи целевую цену (я уведомлю, когда цена упадёт до неё).\n"
        f"Или напиши <b>0</b>, чтобы получать уведомление при любом снижении.",
        parse_mode="HTML",
        reply_markup=back_to_main_kb(),
    )


@router.message(AddItemFSM.waiting_for_target_price)
async def process_target_price(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        value = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число (например: <code>1500</code> или <code>0</code>)", parse_mode="HTML")
        return

    data = await state.get_data()
    target_price = value if value > 0 else None
    notify_any = value == 0

    async with AsyncSessionLocal() as session:
        item = TrackedItem(
            user_id=db_user.id,
            article=data["article"],
            platform=data.get("platform", "wb"),
            name=data["name"],
            last_price=data["price"],
            target_price=target_price,
            notify_any_drop=notify_any,
        )
        session.add(item)
        await session.commit()

    await state.clear()

    target_str = f"Целевая цена: <b>{target_price:.0f} ₽</b>" if target_price else "Уведомление: при любом снижении"
    await message.answer(
        f"🎉 Товар добавлен!\n\n"
        f"📦 <b>{data['name']}</b>\n"
        f"💰 Текущая цена: <b>{data['price']:.0f} ₽</b>\n"
        f"{target_str}\n\n"
        f"Я буду следить за ценой и сообщу при изменении.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


# --- /list и кнопка «Мои товары» ---

@router.message(Command("list"))
@router.callback_query(lambda c: c.data == "my_items")
async def show_my_items(event: Message | CallbackQuery, db_user: User) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrackedItem).where(TrackedItem.user_id == db_user.id)
        )
        items = result.scalars().all()

    if not items:
        text = "📋 Список пуст. Добавь первый товар!"
        kb = main_menu_kb()
    else:
        lines = []
        for i, item in enumerate(items, 1):
            price_str = f"{item.last_price:.0f} ₽" if item.last_price else "—"
            target_str = f" → 🎯{item.target_price:.0f} ₽" if item.target_price else ""
            lines.append(f"{i}. <b>{item.name[:40]}</b>\n   💰 {price_str}{target_str}")
        text = "📋 <b>Твои товары</b>\n🗑 — кнопка справа удаляет товар\n\n" + "\n\n".join(lines)
        kb = items_list_kb(items)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


# --- item_info (заглушка, будущая карточка товара) ---

@router.callback_query(lambda c: c.data and c.data.startswith("item_info:"))
async def item_info(callback: CallbackQuery, db_user: User) -> None:
    item_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        item = await session.get(TrackedItem, item_id)

    if not item or item.user_id != db_user.id:
        await callback.answer("Товар не найден", show_alert=True)
        return

    item_platform = item.platform or "wb"
    url = product_url(item.article, item_platform)
    pname = PLATFORM_NAME.get(item_platform, "магазине")
    emoji = PLATFORM_EMOJI.get(item_platform, "")
    price_str = f"{item.last_price:,.0f} ₽" if item.last_price else "—"
    target_str = f"\n🎯 Цель: {item.target_price:,.0f} ₽" if item.target_price else ""
    await callback.message.edit_text(
        f"{emoji} <b>{item.name}</b>\n"
        f"💰 Цена: {price_str}{target_str}\n"
        f"🔗 <a href='{url}'>Открыть на {pname}</a>",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить из списка", callback_data=f"delete_item:{item_id}")],
            [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="my_items")],
        ])
    )
    await callback.answer()


# --- Удаление товара ---

@router.callback_query(lambda c: c.data and c.data.startswith("delete_item:"))
async def ask_delete_item(callback: CallbackQuery, db_user: User) -> None:
    item_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        item = await session.get(TrackedItem, item_id)

    if not item or item.user_id != db_user.id:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 Удалить товар?\n\n📦 <b>{item.name}</b>",
        parse_mode="HTML",
        reply_markup=confirm_delete_kb(item_id),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm_delete:"))
async def confirm_delete_item(callback: CallbackQuery, db_user: User) -> None:
    item_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        item = await session.get(TrackedItem, item_id)
        if item and item.user_id == db_user.id:
            await session.delete(item)
            await session.commit()

    await callback.message.edit_text(
        "✅ Товар удалён.", reply_markup=main_menu_kb()
    )
    await callback.answer()


# --- Установка целевой цены через список ---

@router.callback_query(lambda c: c.data and c.data.startswith("set_target:"))
async def start_set_target(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    item_id = int(callback.data.split(":")[1])
    await state.set_state(SetTargetFSM.waiting_for_price)
    await state.update_data(item_id=item_id)
    await callback.message.edit_text(
        "🎯 Введи новую целевую цену (в рублях) или <b>0</b> для уведомления при любом снижении:",
        parse_mode="HTML",
        reply_markup=back_to_main_kb(),
    )
    await callback.answer()


@router.message(SetTargetFSM.waiting_for_price)
async def process_new_target(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        value = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число.")
        return

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        item = await session.get(TrackedItem, data["item_id"])
        if item and item.user_id == db_user.id:
            item.target_price = value if value > 0 else None
            item.notify_any_drop = value == 0
            await session.commit()

    await state.clear()
    await message.answer("✅ Целевая цена обновлена!", reply_markup=main_menu_kb())
