"""
wegovy_scraper.py
-----------------
Daily price scraper for Wegovy across 5 Mexican pharmacies.
Run via GitHub Actions cron or locally with: python scrapers/wegovy_scraper.py

Requires: pip install playwright beautifulsoup4 requests
First run: playwright install chromium
"""

import asyncio
import json
import os
import re
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

# ─── CONFIG ──────────────────────────────────────────────────────────────────

DATA_FILE = Path(__file__).parent.parent / "data" / "prices.json"

DOSAGES = ["0.25 mg", "0.5 mg", "1.0 mg", "1.7 mg", "2.4 mg"]

PHARMACY_IDS = ["guadalajara", "ahorro", "benavides", "sfe", "similares"]

# Search terms per pharmacy (adjust if their search engines change)
SEARCH_CONFIG = {
    "guadalajara": {
        "search_url": "https://www.farmaciasguadalajara.com.mx/wps/portal/tienda/busqueda?query={query}",
        "queries": ["wegovy semaglutida", "ozempic 2.4"],
        "price_selector": ".precio, .price, [class*='price']",
    },
    "ahorro": {
        "search_url": "https://www.fahorro.com/search?q={query}",
        "queries": ["wegovy", "semaglutida inyectable"],
        "price_selector": ".price, .product-price, [class*='precio']",
    },
    "benavides": {
        "search_url": "https://www.benavides.com.mx/search?q={query}",
        "queries": ["wegovy semaglutide", "ozempic"],
        "price_selector": ".price-box, .price, [class*='price']",
    },
    "sfe": {
        "search_url": "https://pacientes.sfe.com.mx/catalogo?buscar={query}",
        "queries": ["wegovy", "semaglutida"],
        "price_selector": ".precio, .product-price, [class*='precio']",
    },
    "similares": {
        "search_url": "https://www.farmaciasimilares.com.mx/search?q={query}",
        "queries": ["wegovy ozempic semaglutida"],
        "price_selector": ".price, .precio, [class*='price']",
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─── DATA SCHEMA ─────────────────────────────────────────────────────────────

def load_existing_data() -> dict:
    """Load existing price history from JSON file."""
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)

    # Initialize empty structure
    data = {}
    for ph_id in PHARMACY_IDS:
        data[ph_id] = {}
        for dose in DOSAGES:
            data[ph_id][dose] = []  # List of {date, price} dicts
    return data


def save_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info(f"Saved data to {DATA_FILE}")


# ─── PRICE PARSING ───────────────────────────────────────────────────────────

def extract_price(text: str) -> Optional[float]:
    """Parse MXN price from a string like '$3,200.00' or '3200' or '$ 3,200'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,]", "", text.strip())
    # Handle Mexican format: 3,200.00 or 3200
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def match_dosage(product_name: str) -> Optional[str]:
    """Map a product name to a normalized Wegovy dosage."""
    name = product_name.lower()

    # Skip non-Wegovy products
    if not any(kw in name for kw in ["wegovy", "semaglutida", "semaglutide", "ozempic"]):
        return None

    patterns = {
        "0.25 mg": [r"0\.25\s*mg", r"0,25\s*mg"],
        "0.5 mg":  [r"0\.5\s*mg",  r"0,5\s*mg"],
        "1.0 mg":  [r"1\.0\s*mg",  r"1\s*mg\b"],
        "1.7 mg":  [r"1\.7\s*mg",  r"1,7\s*mg"],
        "2.4 mg":  [r"2\.4\s*mg",  r"2,4\s*mg"],
    }

    for dose, patterns_list in patterns.items():
        for pat in patterns_list:
            if re.search(pat, name):
                return dose
    return None


# ─── SCRAPERS ────────────────────────────────────────────────────────────────

async def scrape_pharmacy(page: Page, pharmacy_id: str) -> dict[str, Optional[float]]:
    """Scrape one pharmacy. Returns {dosage: price_or_None}."""
    config = SEARCH_CONFIG[pharmacy_id]
    results: dict[str, Optional[float]] = {d: None for d in DOSAGES}

    for query in config["queries"]:
        url = config["search_url"].format(query=query.replace(" ", "+"))
        log.info(f"  [{pharmacy_id}] Fetching: {url}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2000)  # Let JS render
            html = await page.content()
        except Exception as e:
            log.warning(f"  [{pharmacy_id}] Failed to load {url}: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Look for structured product cards
        # (Each pharmacy has a different structure — these selectors are starting points)
        product_cards = soup.select(
            ".product-item, .product-card, .item, article[class*='product'], "
            "li[class*='product'], div[class*='product']"
        )

        for card in product_cards:
            # Get product name
            name_el = card.select_one(
                "h2, h3, .product-name, .name, [class*='name'], [class*='title']"
            )
            if not name_el:
                continue

            product_name = name_el.get_text(strip=True)
            dosage = match_dosage(product_name)
            if not dosage:
                continue

            # Get price
            price_el = card.select_one(config["price_selector"])
            if not price_el:
                # Try broader search
                price_el = card.find(string=re.compile(r"\$[\d,]+"))

            if price_el:
                price_text = price_el.get_text(strip=True) if hasattr(price_el, "get_text") else str(price_el)
                price = extract_price(price_text)
                if price and 500 < price < 20000:  # Sanity check: MXN range
                    if results[dosage] is None:  # Take first/cheapest match
                        results[dosage] = price
                        log.info(f"  [{pharmacy_id}] Found {dosage}: ${price:,.0f}")

        # Strategy 2: Fallback - look for any price + dosage patterns in page text
        if all(v is None for v in results.values()):
            page_text = soup.get_text()
            for dose in DOSAGES:
                if results[dose] is not None:
                    continue
                # Try to find price near dosage mention
                dose_pattern = dose.replace(".", r"\.").replace(" ", r"\s*")
                matches = re.finditer(
                    rf"\$\s*([\d,]+(?:\.\d{{2}})?)\s*(?:[^\n]{{0,80}})?{dose_pattern}|"
                    rf"{dose_pattern}(?:[^\n]{{0,80}})?\$\s*([\d,]+(?:\.\d{{2}})?)",
                    page_text,
                )
                for m in matches:
                    raw = m.group(1) or m.group(2)
                    price = extract_price(raw) if raw else None
                    if price and 500 < price < 20000:
                        results[dose] = price
                        log.info(f"  [{pharmacy_id}] (fallback) Found {dose}: ${price:,.0f}")
                        break

    found = sum(1 for v in results.values() if v is not None)
    log.info(f"  [{pharmacy_id}] Done — {found}/{len(DOSAGES)} dosages found")
    return results


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def run_scraper() -> None:
    today = str(date.today())
    log.info(f"Starting Wegovy price scrape for {today}")

    data = load_existing_data()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            locale="es-MX",
        )
        page = await context.new_page()

        for pharmacy_id in PHARMACY_IDS:
            log.info(f"\n{'─'*50}")
            log.info(f"Scraping: {pharmacy_id}")
            try:
                prices = await scrape_pharmacy(page, pharmacy_id)
            except Exception as e:
                log.error(f"Error scraping {pharmacy_id}: {e}")
                prices = {d: None for d in DOSAGES}

            # Append today's results (avoid duplicates)
            for dose in DOSAGES:
                if dose not in data[pharmacy_id]:
                    data[pharmacy_id][dose] = []

                history = data[pharmacy_id][dose]
                existing_dates = [r["date"] for r in history]

                if today not in existing_dates:
                    history.append({"date": today, "price": prices[dose]})
                else:
                    # Update existing entry if we got a price
                    if prices[dose] is not None:
                        for entry in history:
                            if entry["date"] == today:
                                entry["price"] = prices[dose]
                                break
                    log.info(f"  [{pharmacy_id}] {dose}: skipped (already have today's data)")

                # Keep only last 90 days
                history.sort(key=lambda x: x["date"])
                data[pharmacy_id][dose] = history[-90:]

        await browser.close()

    save_data(data)
    log.info(f"\nScrape complete. Data saved to {DATA_FILE}")


if __name__ == "__main__":
    asyncio.run(run_scraper())
