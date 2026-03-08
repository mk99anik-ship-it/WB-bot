from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards.inline import main_menu_kb, back_to_main_kb
from core.models import User
from services.wb_parser import fetch_product, extract_article, WBProduct

router = Router()

FREE_LIMIT = 2
PAID_LIMIT = 4


class CompareFSM(StatesGroup):
    collecting = State()


# ── helpers ──────────────────────────────────────────────────────────────────

def _compare_kb(count: int) -> InlineKeyboardMarkup:
    rows = []
    if count >= 2:
        rows.append([InlineKeyboardButton(text="▶️ Начать сравнение", callback_data="compare_run")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="compare_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _truncate(s: str, n: int = 30) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def _discount_str(p: WBProduct) -> str:
    if p.price_original and p.price_original > p.price:
        pct = round((1 - p.price / p.price_original) * 100)
        return f"{p.price:,.0f} ₽ (-{pct}% от {p.price_original:,.0f} ₽)"
    return f"{p.price:,.0f} ₽"


def _stars(rating: float) -> str:
    filled = round(rating)
    return "★" * filled + "☆" * (5 - filled)


def _format_comparison(products: list[WBProduct]) -> str:
    min_price_idx = min(range(len(products)), key=lambda i: products[i].price)
    max_rating_idx = max(range(len(products)), key=lambda i: products[i].rating)
    max_feedback_idx = max(range(len(products)), key=lambda i: products[i].feedbacks)

    lines = ["📊 <b>Сравнение товаров</b>\n"]
    for i, p in enumerate(products):
        crown = "🏆 " if i == min_price_idx and len(products) > 1 else ""
        lines.append(f"<b>{crown}Товар {i + 1}: {_truncate(p.name)}</b>")
        lines.append(f"🔗 <a href='{p.url}'>Артикул {p.article}</a>")
        lines.append(f"💰 Цена: {_discount_str(p)}")
        if p.brand:
            lines.append(f"🏷 Бренд: {p.brand}")
        if p.supplier:
            sup_r = f" ({p.supplier_rating:.1f}⭐)" if p.supplier_rating else ""
            lines.append(f"🏪 Продавец: {_truncate(p.supplier, 25)}{sup_r}")
        r_crown = "🏆 " if i == max_rating_idx and len(products) > 1 else ""
        lines.append(f"⭐ Рейтинг: {r_crown}{_stars(p.rating)} {p.rating:.1f}")
        f_crown = "🏆 " if i == max_feedback_idx and len(products) > 1 else ""
        lines.append(f"💬 Отзывы: {f_crown}{p.feedbacks:,}")
        lines.append("")

    if len(products) > 1:
        lines.append("🏆 — лучший показатель в категории")

    return "\n".join(lines)


async def _do_comparison(target: Message, state: FSMContext) -> None:
    """Запустить сравнение из накопленного списка."""
    data = await state.get_data()
    items: list[dict] = data.get("products", [])
    await state.clear()

    if len(items) < 2:
        await target.answer("❗ Нужно минимум 2 товара для сравнения.")
        return

    products = [WBProduct(**d) for d in items]
    text = _format_comparison(products)
    await target.answer(text, parse_mode="HTML", disable_web_page_preview=True,
                        reply_markup=back_to_main_kb())


async def _enter_compare_mode(event: Message | CallbackQuery, state: FSMContext,
                              db_user: User) -> None:
    """Войти в режим сравнения (из /compare или кнопки)."""
    limit = PAID_LIMIT if db_user.is_subscribed else FREE_LIMIT
    await state.set_state(CompareFSM.collecting)
    await state.update_data(products=[], limit=limit)

    text = (
        f"⚖️ <b>Режим сравнения</b>\n\n"
        f"Отправляй ссылки или артикулы товаров по одному.\n"
        f"Твой лимит: до <b>{limit}</b> товаров "
        f"({'бесплатно' if not db_user.is_subscribed else 'премиум'}).\n\n"
        f"Минимум 2 товара для старта сравнения."
    )
    kb = _compare_kb(0)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


# ── entry points ─────────────────────────────────────────────────────────────

@router.message(Command("compare"))
async def cmd_compare(message: Message, state: FSMContext, db_user: User) -> None:
    await _enter_compare_mode(message, state, db_user)


@router.callback_query(lambda c: c.data == "compare_help")
async def cb_compare_start(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await _enter_compare_mode(callback, state, db_user)


# ── FSM: получаем товары по одному ──────────────────────────────────────────

@router.message(CompareFSM.collecting)
async def process_compare_item(message: Message, state: FSMContext) -> None:
    article = extract_article(message.text.strip() if message.text else "")
    if not article:
        await message.answer(
            "❌ Не удалось распознать ссылку или артикул.\n"
            "Отправь ссылку на WB или числовой артикул.",
            reply_markup=_compare_kb(0),
        )
        return

    data = await state.get_data()
    items: list[dict] = data.get("products", [])
    limit: int = data.get("limit", FREE_LIMIT)

    if any(p["article"] == article for p in items):
        await message.answer("ℹ️ Этот товар уже есть в списке сравнения.")
        return

    wait_msg = await message.answer("⏳ Загружаю товар…")
    product = await fetch_product(article)
    if product is None:
        await wait_msg.edit_text(
            "❌ Товар не найден на Wildberries. Попробуй другой артикул."
        )
        return

    items.append({
        "article": product.article,
        "name": product.name,
        "price": product.price,
        "url": product.url,
        "price_original": product.price_original,
        "brand": product.brand,
        "supplier": product.supplier,
        "supplier_rating": product.supplier_rating,
        "rating": product.rating,
        "feedbacks": product.feedbacks,
        "qty": product.qty,
    })
    await state.update_data(products=items)

    count = len(items)
    remaining = limit - count

    # Лимит достигнут → сразу запускаем сравнение
    if count >= limit:
        await wait_msg.delete()
        await _do_comparison(message, state)
        return

    names = "\n".join(f"  {i + 1}. {_truncate(p['name'])}" for i, p in enumerate(items))
    if count >= 2:
        hint = f"Добавьте ещё до <b>{remaining}</b> товар(ов) или нажмите «Начать сравнение»."
    else:
        hint = f"Добавьте ещё до <b>{remaining}</b> товар(ов)."

    await wait_msg.edit_text(
        f"✅ <b>Товар {count} добавлен:</b> {_truncate(product.name)}\n\n"
        f"<b>Список:</b>\n{names}\n\n"
        f"{hint}",
        parse_mode="HTML",
        reply_markup=_compare_kb(count),
    )


# ── inline-кнопки внутри режима сравнения ────────────────────────────────────

@router.callback_query(lambda c: c.data == "compare_run")
async def cb_compare_run(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _do_comparison(callback.message, state)


@router.callback_query(lambda c: c.data == "compare_cancel")
async def cb_compare_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Сравнение отменено")
    await callback.message.edit_text("◀️ Сравнение отменено.", reply_markup=main_menu_kb())
