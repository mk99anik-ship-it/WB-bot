import re
import aiohttp
from dataclasses import dataclass, field


@dataclass
class WBProduct:
    article: str
    name: str
    price: float       # цена со скидкой, руб
    url: str
    price_original: float | None = None   # цена без скидки, руб
    brand: str = ""
    supplier: str = ""
    supplier_rating: float = 0.0
    rating: float = 0.0
    feedbacks: int = 0
    qty: int = 0       # остаток на складах


def extract_article(text: str) -> str | None:
    """Извлекает артикул из ссылки WB или из числа."""
    # Из ссылки вида https://www.wildberries.ru/catalog/123456789/detail.aspx
    match = re.search(r"wildberries\.ru/catalog/(\d+)", text)
    if match:
        return match.group(1)
    # Из числа напрямую
    if re.fullmatch(r"\d{5,12}", text.strip()):
        return text.strip()
    return None


async def fetch_product(article: str) -> WBProduct | None:
    """Получает данные о товаре через публичное API Wildberries."""
    url = (
        f"https://card.wb.ru/cards/v4/detail"
        f"?appType=1&curr=rub&dest=-1257786&nm={article}"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://www.wildberries.ru",
        "Referer": "https://www.wildberries.ru/",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        # v4: данные лежат в корне {"products": [...]}
        products = data.get("products", [])
        if not products:
            return None

        product = products[0]
        name = product.get("name", "Неизвестный товар")
        brand = product.get("brand", "")
        supplier = product.get("supplier", "")
        supplier_rating = float(product.get("supplierRating", 0) or 0)
        rating = float(product.get("rating", 0) or 0)
        feedbacks = int(product.get("feedbacks", 0) or 0)

        # Цена лежит в sizes[0].price.product (в копейках)
        sizes = product.get("sizes", [])
        price_kopecks = None
        price_basic_kopecks = None
        total_qty = 0
        for size in sizes:
            price_info = size.get("price", {})
            if not price_kopecks:
                price_kopecks = price_info.get("product") or price_info.get("basic")
            if not price_basic_kopecks:
                price_basic_kopecks = price_info.get("basic")
            for stock in size.get("stocks", []):
                total_qty += int(stock.get("qty", 0))

        if not price_kopecks:
            return None

        price_rub = price_kopecks / 100
        price_original = price_basic_kopecks / 100 if price_basic_kopecks else None

        return WBProduct(
            article=article,
            name=name,
            price=price_rub,
            url=f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
            price_original=price_original,
            brand=brand,
            supplier=supplier,
            supplier_rating=supplier_rating,
            rating=rating,
            feedbacks=feedbacks,
            qty=total_qty,
        )
    except Exception:
        return None
