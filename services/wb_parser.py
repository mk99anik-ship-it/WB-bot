import re
import aiohttp
from dataclasses import dataclass

PLATFORM_WB = "wb"
PLATFORM_NAME = {PLATFORM_WB: "Wildberries"}
PLATFORM_EMOJI = {PLATFORM_WB: "🟣"}

_HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
}


@dataclass
class Product:
    article: str
    name: str
    price: float
    url: str
    platform: str = PLATFORM_WB
    price_original: float | None = None
    brand: str = ""
    supplier: str = ""
    supplier_rating: float = 0.0
    rating: float = 0.0
    feedbacks: int = 0
    qty: int = 0


# Backward-compat alias
WBProduct = Product


def product_url(article: str, platform: str = PLATFORM_WB) -> str:
    return f"https://www.wildberries.ru/catalog/{article}/detail.aspx"


def detect_platform(text: str) -> tuple[str, str] | None:
    """Detects WB product from URL or bare article number."""
    text = text.strip()
    m = re.search(r"wildberries\.ru/catalog/(\d+)", text)
    if m:
        return (PLATFORM_WB, m.group(1))
    if re.fullmatch(r"\d{5,12}", text):
        return (PLATFORM_WB, text)
    return None


def extract_article(text: str) -> str | None:
    result = detect_platform(text)
    if result:
        return result[1]
    return None


async def fetch_product(article_or_id: str, platform: str = PLATFORM_WB) -> Product | None:
    return await _fetch_wb(article_or_id)


async def _fetch_wb(article: str) -> Product | None:
    url = (
        f"https://card.wb.ru/cards/v4/detail"
        f"?appType=1&curr=rub&dest=-1257786&nm={article}"
    )
    headers = {
        **_HEADERS_BROWSER,
        "Accept": "*/*",
        "Origin": "https://www.wildberries.ru",
        "Referer": "https://www.wildberries.ru/",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        products = data.get("products", [])
        if not products:
            return None

        p = products[0]
        sizes = p.get("sizes", [])
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

        return Product(
            article=article,
            name=p.get("name", "Неизвестный товар"),
            price=price_kopecks / 100,
            url=f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
            platform=PLATFORM_WB,
            price_original=price_basic_kopecks / 100 if price_basic_kopecks else None,
            brand=p.get("brand", ""),
            supplier=p.get("supplier", ""),
            supplier_rating=float(p.get("supplierRating", 0) or 0),
            rating=float(p.get("rating", 0) or 0),
            feedbacks=int(p.get("feedbacks", 0) or 0),
            qty=total_qty,
        )
    except Exception:
        return None

PLATFORM_WB = "wb"
PLATFORM_OZON = "ozon"
PLATFORM_ALI = "ali"

PLATFORM_NAME = {
    PLATFORM_WB: "Wildberries",
    PLATFORM_OZON: "Ozon",
    PLATFORM_ALI: "AliExpress",
}

PLATFORM_EMOJI = {
    PLATFORM_WB: "🟣",
    PLATFORM_OZON: "🔵",
    PLATFORM_ALI: "🟠",
}

_HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
}


@dataclass
class Product:
    article: str
    name: str
    price: float
    url: str
    platform: str = PLATFORM_WB
    price_original: float | None = None
    brand: str = ""
    supplier: str = ""
    supplier_rating: float = 0.0
    rating: float = 0.0
    feedbacks: int = 0
    qty: int = 0


# Backward-compat alias
WBProduct = Product


def product_url(article: str, platform: str) -> str:
    """Builds product page URL for a given platform."""
    if platform == PLATFORM_OZON:
        return f"https://www.ozon.ru/product/{article}/"
    if platform == PLATFORM_ALI:
        return f"https://aliexpress.ru/item/{article}.html"
    return f"https://www.wildberries.ru/catalog/{article}/detail.aspx"


def detect_platform(text: str) -> tuple[str, str] | None:
    """
    Detects marketplace and product identifier from a URL or article number.
    Returns (platform, identifier) or None if not recognised.
    """
    text = text.strip()

    # Wildberries link
    m = re.search(r"wildberries\.ru/catalog/(\d+)", text)
    if m:
        return (PLATFORM_WB, m.group(1))
    # WB bare article (5-12 digits)
    if re.fullmatch(r"\d{5,12}", text):
        return (PLATFORM_WB, text)

    # Ozon product link  e.g. ozon.ru/product/name-123456/
    m = re.search(r"ozon\.ru/product/(?:[^\s/]+-)?(\d+)/?", text)
    if m:
        return (PLATFORM_OZON, m.group(1))
    # Ozon short link
    if re.search(r"ozon\.ru/t/\S+", text):
        return (PLATFORM_OZON, text)  # pass full URL to resolver

    # AliExpress  aliexpress.ru/item/123.html  or  aliexpress.com/item/123.html
    m = re.search(r"aliexpress\.(?:ru|com)/item/(\d+)\.html", text)
    if m:
        return (PLATFORM_ALI, m.group(1))
    # Other AliExpress short/redirect links containing a long numeric ID
    if "aliexpress" in text:
        m = re.search(r"/(\d{10,})", text)
        if m:
            return (PLATFORM_ALI, m.group(1))

    return None


def extract_article(text: str) -> str | None:
    """Legacy helper: returns WB article or None."""
    result = detect_platform(text)
    if result and result[0] == PLATFORM_WB:
        return result[1]
    return None


async def fetch_product(article_or_id: str, platform: str = PLATFORM_WB) -> Product | None:
    """Unified product fetcher. Dispatches to the right marketplace parser."""
    if platform == PLATFORM_WB:
        return await _fetch_wb(article_or_id)
    if platform == PLATFORM_OZON:
        return await _fetch_ozon(article_or_id)
    if platform == PLATFORM_ALI:
        return await _fetch_ali(article_or_id)
    return None


# ── Wildberries ───────────────────────────────────────────────────────────────

async def _fetch_wb(article: str) -> Product | None:
    url = (
        f"https://card.wb.ru/cards/v4/detail"
        f"?appType=1&curr=rub&dest=-1257786&nm={article}"
    )
    headers = {
        **_HEADERS_BROWSER,
        "Accept": "*/*",
        "Origin": "https://www.wildberries.ru",
        "Referer": "https://www.wildberries.ru/",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        products = data.get("products", [])
        if not products:
            return None

        p = products[0]
        sizes = p.get("sizes", [])
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

        return Product(
            article=article,
            name=p.get("name", "Неизвестный товар"),
            price=price_kopecks / 100,
            url=f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
            platform=PLATFORM_WB,
            price_original=price_basic_kopecks / 100 if price_basic_kopecks else None,
            brand=p.get("brand", ""),
            supplier=p.get("supplier", ""),
            supplier_rating=float(p.get("supplierRating", 0) or 0),
            rating=float(p.get("rating", 0) or 0),
            feedbacks=int(p.get("feedbacks", 0) or 0),
            qty=total_qty,
        )
    except Exception:
        return None


# ── Ozon ──────────────────────────────────────────────────────────────────────

async def _fetch_ozon(ozon_id: str) -> Product | None:
    """Scrape Ozon product page and extract data from JSON-LD."""
    url = ozon_id if ozon_id.startswith("http") else f"https://www.ozon.ru/product/{ozon_id}/"
    headers = {
        **_HEADERS_BROWSER,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
                final_url = str(resp.url)

        # Extract real numeric ID from redirected URL
        m = re.search(r"ozon\.ru/product/(?:[^\s/]+-)?(\d+)/?", final_url)
        real_id = m.group(1) if m else ozon_id

        # Try JSON-LD blocks
        for ld_text in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL,
        ):
            try:
                data = json.loads(ld_text.strip())
                for item in (data if isinstance(data, list) else [data]):
                    if item.get("@type") != "Product":
                        continue
                    name = item.get("name", "")
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = float(offers.get("price", 0) or 0)
                    agg = item.get("aggregateRating", {})
                    brand_info = item.get("brand", {})
                    if name and price > 0:
                        return Product(
                            article=real_id,
                            name=name,
                            price=price,
                            url=f"https://www.ozon.ru/product/{real_id}/",
                            platform=PLATFORM_OZON,
                            brand=brand_info.get("name", "") if isinstance(brand_info, dict) else "",
                            rating=float(agg.get("ratingValue", 0) or 0),
                            feedbacks=int(agg.get("reviewCount", 0) or 0),
                        )
            except (json.JSONDecodeError, ValueError, KeyError):
                continue

        # Fallback: embedded state JSON
        m_price = re.search(r'"finalPrice":\s*"?(\d+(?:\.\d+)?)"?', html)
        m_name = re.search(r'"title":\s*"([^"]{5,200})"', html)
        if m_price and m_name:
            return Product(
                article=real_id,
                name=m_name.group(1),
                price=float(m_price.group(1)),
                url=f"https://www.ozon.ru/product/{real_id}/",
                platform=PLATFORM_OZON,
            )
    except Exception:
        pass
    return None


# ── AliExpress ────────────────────────────────────────────────────────────────

async def _fetch_ali(ali_id: str) -> Product | None:
    """Scrape AliExpress product page and extract data from JSON-LD / embedded JS."""
    url = ali_id if ali_id.startswith("http") else f"https://aliexpress.ru/item/{ali_id}.html"
    headers = {
        **_HEADERS_BROWSER,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
                final_url = str(resp.url)

        m = re.search(r"/item/(\d+)\.html", final_url)
        real_id = m.group(1) if m else ali_id

        # Try JSON-LD
        for ld_text in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL,
        ):
            try:
                data = json.loads(ld_text.strip())
                for item in (data if isinstance(data, list) else [data]):
                    if item.get("@type") not in ("Product", "ItemPage"):
                        continue
                    name = item.get("name", "")
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = float(offers.get("price", 0) or 0)
                    agg = item.get("aggregateRating", {})
                    if name and price > 0:
                        return Product(
                            article=real_id,
                            name=name,
                            price=price,
                            url=f"https://aliexpress.ru/item/{real_id}.html",
                            platform=PLATFORM_ALI,
                            rating=float(agg.get("ratingValue", 0) or 0),
                            feedbacks=int(agg.get("reviewCount", 0) or 0),
                        )
            except (json.JSONDecodeError, ValueError, KeyError):
                continue

        # Fallback: window.runParams embedded data
        m_price = re.search(r'"minActivityAmount":\{"value":"?(\d+(?:\.\d+)?)"?', html)
        if not m_price:
            m_price = re.search(r'"salePrice":\{"minAmount":"?(\d+(?:\.\d+)?)"?', html)
        m_name = re.search(r'"subject":\s*"([^"]{5,300})"', html)
        if not m_name:
            m_name = re.search(r'<title>([^<]{10,200})</title>', html)
        if m_price and m_name:
            name = m_name.group(1)
            for suffix in (" — AliExpress", " - AliExpress", " | AliExpress"):
                name = name.split(suffix)[0]
            name = name.strip()
            try:
                return Product(
                    article=real_id,
                    name=name,
                    price=float(m_price.group(1)),
                    url=f"https://aliexpress.ru/item/{real_id}.html",
                    platform=PLATFORM_ALI,
                )
            except ValueError:
                pass
    except Exception:
        pass
    return None
