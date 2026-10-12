import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data-lake" / "silver" / "airbnb_silver.db"

columns_to_check = [
    "price",
    "price_quote_total_price",
    "price_quote_price_per_night",
    "bedrooms",
    "beds",
    "bathrooms",
    "bathrooms_text",
    "accommodates",
    "minimum_nights",
    "maximum_nights",
    "latitude",
    "longitude",
    "last_scraped",
    "calendar_last_scraped",
    "first_review",
    "last_review",
    "host_id",
    "neighbourhood_cleansed",
]

with sqlite3.connect(DB) as conn:
    for column in columns_to_check:
        # Comprobar que la columna existe.
        available = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(listings_snapshot)"
            )
        }

        if column not in available:
            print(f"\n{column}: columna no encontrada")
            continue

        quoted = '"' + column.replace('"', '""') + '"'

        print(f"\n--- {column} ---")

        result = conn.execute(
            f"""
            SELECT {quoted}, COUNT(*) AS n
            FROM listings_snapshot
            WHERE {quoted} IS NOT NULL
              AND TRIM({quoted}) <> ''
            GROUP BY {quoted}
            ORDER BY n DESC
            LIMIT 8
            """
        )

        for value, count in result:
            print(f"{value!r}: {count}")
