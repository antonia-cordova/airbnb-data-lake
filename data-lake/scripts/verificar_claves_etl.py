import csv
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_DIR / "data-lake" / "bronze"

DATASETS = {
    "listings": (
        BRONZE_DIR / "listings" / "unido" / "listings_unido.csv",
        "id",
    ),
    "reviews": (
        BRONZE_DIR / "reviews" / "unido" / "reviews_unido.csv",
        "id",
    ),
}

EXPECTED_FILES = {
    "listings-MARCH.csv",
    "listings-JUNE.csv",
    "listings-SEP.csv",
    "reviews-MARCH.csv",
    "reviews-JUNE.csv",
    "reviews-SEP.csv",
}


def main():
    for dataset, (path, id_column) in DATASETS.items():
        print(f"\n{'=' * 60}\n{dataset.upper()}\n{'=' * 60}")

        counts = Counter()
        missing_ids = Counter()
        seen_ids = set()
        duplicate_ids = Counter()
        missing_source = 0

        with path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.DictReader(file)

            required = {id_column, "_source_file"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(
                    f"Faltan columnas requeridas en {path.name}"
                )

            for row in reader:
                source = row["_source_file"].strip()
                record_id = row[id_column].strip()

                if not source:
                    missing_source += 1
                    continue

                counts[source] += 1

                if not record_id:
                    missing_ids[source] += 1
                    continue

                key = (source, record_id)

                if key in seen_ids:
                    duplicate_ids[source] += 1
                else:
                    seen_ids.add(key)

        print(f"Filas totales: {sum(counts.values())}")
        print("Filas por archivo de origen:")

        for source, count in sorted(counts.items()):
            print(f"  {source}: {count:,}")

        print(f"Filas sin _source_file: {missing_source}")
        print(f"IDs vacíos por archivo: {dict(missing_ids)}")
        print(f"IDs duplicados por archivo: {dict(duplicate_ids)}")

        actual_files = set(counts)
        expected = {
            name for name in EXPECTED_FILES
            if name.startswith(dataset + "-")
        }

        print(f"Archivos esperados presentes: {actual_files == expected}")

        if actual_files != expected:
            print(f"  Esperados: {sorted(expected)}")
            print(f"  Encontrados: {sorted(actual_files)}")

        if missing_source or missing_ids or duplicate_ids:
            raise ValueError(
                f"Falló la validación de claves para {dataset}"
            )

        if actual_files != expected:
            raise ValueError(
                f"Los archivos de origen no coinciden para {dataset}"
            )

    print("\nValidación de claves completada correctamente.")


if __name__ == "__main__":
    main()
