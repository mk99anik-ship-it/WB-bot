import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

    SUBSCRIPTION_PRICE_STARS: int = int(os.getenv("SUBSCRIPTION_PRICE_STARS", "50"))
    SUBSCRIPTION_DAYS: int = int(os.getenv("SUBSCRIPTION_DAYS", "30"))

    FREE_ITEMS_LIMIT: int = int(os.getenv("FREE_ITEMS_LIMIT", "1"))
    PAID_ITEMS_LIMIT: int = int(os.getenv("PAID_ITEMS_LIMIT", "20"))

    FREE_CHECK_INTERVAL: int = int(os.getenv("FREE_CHECK_INTERVAL", "120"))
    PAID_CHECK_INTERVAL: int = int(os.getenv("PAID_CHECK_INTERVAL", "30"))

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./wb_monitor.db")


config = Config()
