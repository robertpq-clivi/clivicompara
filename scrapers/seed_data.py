"""
seed_data.py
------------
Generates 30 days of realistic initial price history and saves to data/prices.json.
Run once to bootstrap the dashboard before the first real scrape.

Usage: python scrapers/seed_data.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "prices.json"

PHARMACIES = ["guadalajara", "ahorro", "benavides", "sfe", "similares"]
DOSAGES = ["0.25 mg", "0.5 mg", "1.0 mg", "1.7 mg", "2.4 mg"]

BASE_PRICES = {
    "guadalajara": {"0.25 mg": 2800, "0.5 mg": 3200, "1.0 mg": 4100, "1.7 mg": 5200, "2.4 mg": 6800},
    "ahorro":      {"0.25 mg": 2650, "0.5 mg": 3050, "1.0 mg": 3950, "1.7 mg": 5000, "2.4 mg": 6500},
    "benavides":   {"0.25 mg": 2900, "0.5 mg": 3300, "1.0 mg": 4200, "1.7 mg": 5300, "2.4 mg": 6900},
    "sfe":         {"0.25 mg": 2550, "0.5 mg": 2950, "1.0 mg": 3800, "1.7 mg": 4900, "2.4 mg": 6200},
    "similares":   {"0.25 mg": None, "0.5 mg": 3100, "1.0 mg": 4050, "1.7 mg": 5100, "2.4 mg": None},
}


def generate_history(base, days=30, seed=None):
    if base is None:
        return [{"date": str(date.today() - timedelta(days=days - 1 - i)), "price": None}
                for i in range(days)]
    rng = random.Random(seed or base)
    cur = base * (0.92 + rng.random() * 0.08)
    entries = []
    for i in range(days):
        day = date.today() - timedelta(days=days - 1 - i)
        drift = (rng.random() - 0.49) * 0.025
        spike = (rng.random() - 0.5) * 0.08 if rng.random() < 0.05 else 0
        cur = max(base * 0.75, min(base * 1.25, cur * (1 + drift + spike)))
        entries.append({"date": str(day), "price": round(cur)})
    return entries


data = {}
for ph in PHARMACIES:
    data[ph] = {}
    for dose in DOSAGES:
        base = BASE_PRICES[ph][dose]
        data[ph][dose] = generate_history(base, days=30, seed=hash(f"{ph}{dose}") % 99999)

DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(DATA_FILE, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Seeded {sum(len(v) for d in data.values() for v in d.values())} entries → {DATA_FILE}")
