from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from bot.keyboards.inline import main_menu_kb, back_to_main_kb
from core.models import User

router = Router()

WELCOME_TEXT = (
    "👋 <b>Привет! Я бот для мониторинга цен.</b>\n\n"
    "Слежу за ценами на нужные тебе товары и сообщаю, когда цена падает.\n\n"
    "<b>Поддерживаю магазины:</b>\n"
    "🟣 Wildberries • 🔵 Ozon • 🟠 AliExpress\n\n"
    "<b>Возможности:</b>\n"
    "• 🆓 Бесплатно: отслеживание 1 товара, проверка раз в 2 часа\n"
    "• ⭐ Подписка: до 20 товаров, проверка каждые 30 мин\n\n"
    "Выбери действие:"
)

HELP_TEXT = (
    "ℹ️ <b>Как пользоваться ботом:</b>\n\n"
    "1️⃣ Нажми <b>«Добавить товар»</b>\n"
    "2️⃣ Отправь ссылку на товар с любого магазина:\n"
    "   🟣 <code>https://www.wildberries.ru/catalog/123456789/detail.aspx</code>\n"
    "   🔵 <code>https://www.ozon.ru/product/название-123456789/</code>\n"
    "   🟠 <code>https://aliexpress.ru/item/1005001234567890.html</code>\n"
    "   или артикул WB: <code>123456789</code>\n\n"
    "3️⃣ Опционально — установи целевую цену. Получишь уведомление, когда цена достигнет её\n\n"
    "4️⃣ Я буду следить за ценой и сразу напишу при снижении!\n\n"
    "<b>Команды:</b>\n"
    "/start — главное меню\n"
    "/help — эта справка\n"
    "/add — добавить товар\n"
    "/list — мои товары\n"
    "/sub — управление подпиской\n"
    "/compare 123 456 — сравнить товары (до 2 бесплатно, до 4 с премиумом)\n"
    "/share — поделиться вишлистом\n"
    "/digest on 9:00 — ежедневная сводка цен\n"
    "/digest off — выключить дайджест\n\n"
    "<b>Команды администратора:</b>\n"
    "/grant &lt;id&gt; [дней] — выдать премиум\n"
    "/revoke &lt;id&gt; — забрать премиум\n"
    "/users — список пользователей"
)


ONBOARDING_TEXT = (
    "🌟 <b>Добро пожаловать! Вот что я умею:</b>\n\n"
    "🔔 <b>Отслеживаю цены</b>\n"
    "Добавь товар по ссылке или артикулу — я сообщу, когда цена упадёт.\n"
    "<code>/add</code> или кнопка <b>«Добавить товар»</b>\n\n"
    "⚖️ <b>Сравниваю товары</b>\n"
    "Дай два артикула — покажу цены, рейтинг, отзывы и остаток рядом.\n"
    "<code>/compare 123456 789012</code>\n\n"
    "☀️ <b>Утренний дайджест</b>\n"
    "Каждое утро шлю сводку: что подешевело за ночь и общая сумма вишлиста.\n"
    "Кнопка <b>«☀️ Дайджест»</b> → выбери удобное время\n\n"
    "📤 <b>Делюсь списком желаний</b>\n"
    "Красиво оформлю список с ценами и ссылками — можно переслать подруге.\n"
    "<code>/share</code>\n\n"
    "⭐ <b>Бесплатно</b>: 1 товар, проверка раз в 2 часа\n"
    "💎 <b>Подписка</b>: до 20 товаров, проверка каждые 30 мин, сравнение до 4 товаров\n\n"
    "Начнём? 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message, is_new_user: bool = False) -> None:
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())
    if is_new_user:
        await message.answer(ONBOARDING_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=back_to_main_kb())


@router.callback_query(lambda c: c.data == "back_main")
async def cb_back_main(callback: CallbackQuery) -> None:
    await callback.message.edit_text(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(HELP_TEXT, parse_mode="HTML", reply_markup=back_to_main_kb())
    await callback.answer()
