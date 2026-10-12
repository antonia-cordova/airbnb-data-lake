import csv
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_FILE = (
    PROJECT_DIR / "data-lake" / "bronze" / "listings" /
    "unido" / "listings_unido.csv"
)
REPORT_DIR = PROJECT_DIR / "data-lake" / "reportes"

SNAPSHOTS = {"MARCH", "JUNE", "SEP"}


def main():
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(INPUT_FILE)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Contadores de valores vacíos por snapshot y columna.
    total_rows = Counter()
    empty_counts = Counter()
    explicit_tokens = Counter()
    snapshots_found = set()

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("El CSV no tiene encabezados.")

        columns = [
            column for column in reader.fieldnames
            if column != "_source_file"
        ]

        for row in reader:
            source = (row.get("_source_file") or "").strip()

            if not source.startswith("listings-") or not source.endswith(".csv"):
                raise ValueError(f"_source_file inesperado: {source!r}")

            snapshot = source[len("listings-"):-4]
            if snapshot not in SNAPSHOTS:
                raise ValueError(f"Snapshot desconocido: {snapshot}")

            snapshots_found.add(snapshot)
            total_rows[snapshot] += 1

            for column in columns:
                value = row.get(column)

                if value is None or value.strip() == "":
                    empty_counts[(snapshot, column)] += 1
                elif value.strip().lower() in {"na", "n/a", "null", "none"}:
                    # Se reportan aparte: no los tratamos como vacíos.
                    explicit_tokens[(snapshot, column, value.strip())] += 1

    if snapshots_found != SNAPSHOTS:
        raise ValueError(
            f"Se esperaban {sorted(SNAPSHOTS)}, "
            f"pero se encontraron {sorted(snapshots_found)}"
        )

    detail_path = REPORT_DIR / "null_audit_by_snapshot.csv"
    summary_path = REPORT_DIR / "null_audit_summary.csv"

    with detail_path.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "snapshot", "column", "total_rows",
            "empty_count", "empty_percent"
        ])

        for snapshot in sorted(SNAPSHOTS):
            for column in columns:
                total = total_rows[snapshot]
                empty = empty_counts[(snapshot, column)]
                percent = 100 * empty / total if total else 0
                writer.writerow([
                    snapshot, column, total, empty, f"{percent:.4f}"
                ])

    with summary_path.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "column", "total_rows_all_snapshots",
            "empty_count", "empty_percent",
            "max_snapshot_empty_percent"
        ])

        total_all = sum(total_rows.values())

        for column in columns:
            empty_all = sum(
                empty_counts[(snapshot, column)]
                for snapshot in SNAPSHOTS
            )
            percentages = [
                100 * empty_counts[(snapshot, column)] / total_rows[snapshot]
                for snapshot in SNAPSHOTS
            ]
            writer.writerow([
                column,
                total_all,
                empty_all,
                f"{100 * empty_all / total_all:.4f}",
                f"{max(percentages):.4f}",
            ])

    print(f"Filas analizadas: {sum(total_rows.values()):,}")
    print(f"Snapshots encontrados: {', '.join(sorted(snapshots_found))}")
    print(f"Columnas analizadas: {len(columns)}")
    print(f"\nInforme detallado: {detail_path}")
    print(f"Resumen: {summary_path}")

    print("\nColumnas con más valores vacíos:")
    ranked = sorted(
        columns,
        key=lambda col: sum(
            empty_counts[(snapshot, col)]
            for snapshot in SNAPSHOTS
        ),
        reverse=True,
    )

    for column in ranked[:20]:
        empty = sum(
            empty_counts[(snapshot, column)]
            for snapshot in SNAPSHOTS
        )
        percent = 100 * empty / sum(total_rows.values())
        print(f"  {column}: {empty:,} ({percent:.2f}%)")

    print("\nTokens explícitos detectados (no clasificados como vacíos):")
    if explicit_tokens:
        for (snapshot, column, token), count in sorted(explicit_tokens.items()):
            print(f"  {snapshot} | {column} | {token}: {count}")
    else:
        print("  Ninguno")


if __name__ == "__main__":
    main()
