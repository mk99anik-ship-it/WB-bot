from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_item")],
        [InlineKeyboardButton(text="📋 Мои товары", callback_data="my_items")],
        [
            InlineKeyboardButton(text="⭐ Подписка", callback_data="subscription"),
            InlineKeyboardButton(text="☀️ Дайджест", callback_data="digest_menu"),
        ],
        [
            InlineKeyboardButton(text="⚖️ Сравнить товары", callback_data="compare_help"),
            InlineKeyboardButton(text="📤 Поделиться", callback_data="share_wishlist"),
        ],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
    ])


def items_list_kb(items: list) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        price_str = f"{item.last_price:.0f} ₽" if item.last_price else "—"
        buttons.append([
            InlineKeyboardButton(
                text=f"{item.name[:28]} — {price_str}",
                callback_data=f"item_info:{item.id}",
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"delete_item:{item.id}",
            ),
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_kb(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{item_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="my_items"),
        ]
    ])


def subscription_kb(is_subscribed: bool) -> InlineKeyboardMarkup:
    pay_text = "🔄 Продлить подписку" if is_subscribed else "⭐ Оплатить подписку"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=pay_text, callback_data="pay_subscription")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


def set_target_price_kb(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Установить целевую цену", callback_data=f"set_target:{item_id}")],
        [InlineKeyboardButton(text="◀️ К списку", callback_data="my_items")],
    ])


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])


TIME_PRESETS = [
    ("7:00", 7, 0), ("8:00", 8, 0), ("9:00", 9, 0),
    ("10:00", 10, 0), ("18:00", 18, 0), ("21:00", 21, 0),
]


def digest_menu_kb(digest_hour: int | None, digest_minute: int | None) -> InlineKeyboardMarkup:
    """Меню настройки дайджеста."""
    buttons = []

    if digest_hour is not None:
        # Дайджест включён — показываем кнопку выключения
        buttons.append([
            InlineKeyboardButton(
                text=f"🔔 Выключить ({digest_hour:02d}:{digest_minute:02d})",
                callback_data="digest_off"
            )
        ])
        buttons.append([InlineKeyboardButton(text="🕒 Изменить время:", callback_data="digest_noop")])
    else:
        buttons.append([InlineKeyboardButton(text="⏰ Выбери время рассылки:", callback_data="digest_noop")])

    # Кнопки пресетов времени — по 3 в ряд
    row = []
    for label, h, m in TIME_PRESETS:
        active = (digest_hour == h and digest_minute == m)
        btn_text = f"✅ {label}" if active else label
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"digest_set:{h}:{m}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
