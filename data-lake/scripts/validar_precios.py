import sqlite3
from pathlib import Path
from decimal import Decimal, InvalidOperation

DB = Path("data-lake/silver/airbnb_silver.db")

def parse_price(value):
    if value is None or not value.strip():
        return None

    normalized = value.strip().replace("$", "").replace(",", "")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return "INVALID"

with sqlite3.connect(DB) as conn:
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT snapshot_id, id, price,
               price_quote_price_per_night,
               price_quote_total_price
        FROM listings_snapshot
    """).fetchall()

results = {}

for snapshot in ("MARCH", "JUNE", "SEP"):
    data = [r for r in rows if r["snapshot_id"] == snapshot]

    invalid_price = 0
    invalid_nightly = 0
    invalid_total = 0
    comparable = 0
    different = 0

    for row in data:
        price = parse_price(row["price"])
        nightly = parse_price(row["price_quote_price_per_night"])
        total = parse_price(row["price_quote_total_price"])

        if price == "INVALID":
            invalid_price += 1
        if nightly == "INVALID":
            invalid_nightly += 1
        if total == "INVALID":
            invalid_total += 1

        if isinstance(price, Decimal) and isinstance(nightly, Decimal):
            comparable += 1
            if price != nightly:
                different += 1

    results[snapshot] = {
        "filas": len(data),
        "price_invalidos": invalid_price,
        "precio_noche_invalidos": invalid_nightly,
        "total_invalidos": invalid_total,
        "price_vs_noche_comparables": comparable,
        "price_vs_noche_diferentes": different,
    }

for snapshot, result in results.items():
    print(f"\n{snapshot}")
    for key, value in result.items():
        print(f"  {key}: {value}")
