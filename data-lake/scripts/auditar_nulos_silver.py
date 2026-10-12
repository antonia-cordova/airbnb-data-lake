import sqlite3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_FILE = ROOT / "data-lake" / "silver" / "airbnb_silver.db"
REPORT_DIR = ROOT / "data-lake" / "reportes"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

with sqlite3.connect(DB_FILE) as conn:
    conn.row_factory = sqlite3.Row

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM listings_snapshot"
    ).fetchone()[0]

    columns = conn.execute(
        "PRAGMA table_info(listings_snapshot)"
    ).fetchall()

    data_columns = [
        column["name"]
        for column in columns
        if column["name"] not in {"snapshot_id", "source_file"}
    ]

    snapshots = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT snapshot_id "
            "FROM listings_snapshot ORDER BY snapshot_id"
        )
    ]

    detailed_results = []
    summary_results = []

    for column in data_columns:
        quoted_column = '"' + column.replace('"', '""') + '"'

        null_count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM listings_snapshot
            WHERE {quoted_column} IS NULL
               OR TRIM({quoted_column}) = ''
            """
        ).fetchone()[0]

        summary_results.append({
            "column": column,
            "total_rows": total_rows,
            "null_count": null_count,
            "null_percentage": round(
                null_count / total_rows * 100, 4
            ) if total_rows else 0,
        })

        for snapshot in snapshots:
            snapshot_total = conn.execute(
                """
                SELECT COUNT(*)
                FROM listings_snapshot
                WHERE snapshot_id = ?
                """,
                (snapshot,),
            ).fetchone()[0]

            snapshot_nulls = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM listings_snapshot
                WHERE snapshot_id = ?
                  AND (
                      {quoted_column} IS NULL
                      OR TRIM({quoted_column}) = ''
                  )
                """,
                (snapshot,),
            ).fetchone()[0]

            detailed_results.append({
                "snapshot": snapshot,
                "column": column,
                "total_rows": snapshot_total,
                "null_count": snapshot_nulls,
                "null_percentage": round(
                    snapshot_nulls / snapshot_total * 100, 4
                ) if snapshot_total else 0,
            })

summary_results.sort(
    key=lambda item: item["null_percentage"], reverse=True
)

summary_path = REPORT_DIR / "null_audit_silver_summary.csv"
detail_path = REPORT_DIR / "null_audit_silver_by_snapshot.csv"

with summary_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=summary_results[0].keys())
    writer.writeheader()
    writer.writerows(summary_results)

with detail_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=detailed_results[0].keys())
    writer.writeheader()
    writer.writerows(detailed_results)

print(f"Filas auditadas: {total_rows:,}")
print(f"Columnas auditadas: {len(data_columns)}")
print(f"Snapshots: {', '.join(snapshots)}")
print(f"\nResumen: {summary_path}")
print(f"Detalle por snapshot: {detail_path}")

print("\n20 columnas con mayor porcentaje de nulos:")
for item in summary_results[:20]:
    print(
        f"{item['column']}: "
        f"{item['null_count']:,} "
        f"({item['null_percentage']:.2f}%)"
    )
