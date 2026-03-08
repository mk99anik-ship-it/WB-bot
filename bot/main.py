import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from core.config import config
from core.database import init_db
from bot.handlers import start, tracking, subscription, admin, digest, compare, share
from bot.middlewares.user import UserMiddleware
from services.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not config.BOT_TOKEN or config.BOT_TOKEN == "your_bot_token_here":
        raise RuntimeError("Укажи BOT_TOKEN в файле .env")

    # Инициализация базы данных
    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware для автосоздания пользователей
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(tracking.router)
    dp.include_router(subscription.router)
    dp.include_router(admin.router)
    dp.include_router(digest.router)
    dp.include_router(compare.router)
    dp.include_router(share.router)

    # Запуск планировщика
    scheduler = create_scheduler(bot)
    scheduler.start()
    logger.info("Планировщик запущен")

    # Команды в меню (значок слева от поля ввода)
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="add", description="➕ Добавить товар"),
        BotCommand(command="list", description="📋 Мои товары"),
        BotCommand(command="compare", description="⚖️ Сравнить товары"),
        BotCommand(command="share", description="📤 Поделиться вишлистом"),
        BotCommand(command="digest", description="☀️ Настройка дайджеста"),
        BotCommand(command="sub", description="⭐ Подписка"),
        BotCommand(command="help", description="ℹ️ Помощь"),
    ])

    logger.info("Бот запущен. Нажми Ctrl+C для остановки.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
