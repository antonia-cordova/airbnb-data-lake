import csv
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_DIR / "data-lake" / "bronze"
DB_FILE = PROJECT_DIR / "data-lake" / "silver" / "airbnb_silver.db"

DATASETS = {
    "listings_snapshot": (
        BRONZE_DIR / "listings" / "unido" / "listings_unido.csv",
        "id",
    ),
    "reviews_snapshot": (
        BRONZE_DIR / "reviews" / "unido" / "reviews_unido.csv",
        "id",
    ),
}


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def main():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        for table, (csv_path, primary_id) in DATASETS.items():
            if not csv_path.is_file():
                raise FileNotFoundError(csv_path)

            with csv_path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.reader(file)
                columns = next(reader)

            if len(columns) != len(set(columns)):
                raise ValueError(
                    f"Hay columnas repetidas en {csv_path.name}"
                )

            if primary_id not in columns:
                raise ValueError(
                    f"No existe la columna {primary_id!r} en {csv_path.name}"
                )

            # _source_file se conserva como source_file, separado
            # de las columnas originales
            source_columns = [
                column for column in columns
                if column != "_source_file"
            ]

            if "snapshot_id" in source_columns:
                raise ValueError(
                    f"La columna snapshot_id ya existe en {csv_path.name}"
                )

            definitions = [
                '"snapshot_id" TEXT NOT NULL',
                '"source_file" TEXT NOT NULL',
            ]

            definitions.extend(
                f"{quote_identifier(column)} TEXT"
                for column in source_columns
            )

            definitions.append(
                f"PRIMARY KEY "
                f"({quote_identifier('snapshot_id')}, "
                f"{quote_identifier(primary_id)})"
            )

            sql = (
                f"CREATE TABLE IF NOT EXISTS {quote_identifier(table)} "
                f"({', '.join(definitions)})"
            )

            conn.execute(sql)

            print(f"\nTabla: {table}")
            print(f"Archivo de origen: {csv_path.name}")
            print(f"Columnas originales: {len(source_columns)}")
            print("Clave primaria: (snapshot_id, id)")

        conn.commit()

    print("\nTablas preparadas correctamente.")


if __name__ == "__main__":
    main()
