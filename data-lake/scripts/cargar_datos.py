import csv
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_DIR / "data-lake" / "bronze"
DB_FILE = PROJECT_DIR / "data-lake" / "silver" / "airbnb_silver.db"

BATCH_SIZE = 5000

DATASETS = {
    "listings": {
        "table": "listings_snapshot",
        "path": BRONZE_DIR / "listings" / "unido" / "listings_unido.csv",
        "id_column": "id",
        "prefix": "listings-",
    },
    "reviews": {
        "table": "reviews_snapshot",
        "path": BRONZE_DIR / "reviews" / "unido" / "reviews_unido.csv",
        "id_column": "id",
        "prefix": "reviews-",
    },
}


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def snapshot_from_source(source_file, prefix):
    if not source_file.startswith(prefix) or not source_file.endswith(".csv"):
        raise ValueError(f"Archivo de origen inesperado: {source_file}")

    label = source_file[len(prefix):-4]

    if label not in {"MARCH", "JUNE", "SEP"}:
        raise ValueError(f"Snapshot no reconocido: {source_file}")

    return label


def load_dataset(dataset_name):
    config = DATASETS[dataset_name]
    table = config["table"]
    path = config["path"]
    id_column = config["id_column"]

    if not path.is_file():
        raise FileNotFoundError(path)

    run_id = None
    loaded_rows = 0
    source_rows = 0
    started_at = now_utc()

    with sqlite3.connect(DB_FILE, timeout=60) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 60000")

        cursor = conn.execute(
            """
            INSERT INTO etl_runs
                (dataset_name, started_at, status, source_rows, loaded_rows)
            VALUES (?, ?, 'RUNNING', 0, 0)
            """,
            (dataset_name, started_at),
        )
        run_id = cursor.lastrowid
        conn.commit()

        try:
            with path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.DictReader(file)
                original_columns = reader.fieldnames

                if not original_columns:
                    raise ValueError(f"CSV sin encabezados: {path}")

                if len(original_columns) != len(set(original_columns)):
                    raise ValueError(f"Hay columnas repetidas: {path}")

                required = {"id", "_source_file"}
                if not required.issubset(original_columns):
                    raise ValueError(
                        f"Faltan columnas requeridas: {required - set(original_columns)}"
                    )

                data_columns = [
                    column for column in original_columns
                    if column != "_source_file"
                ]

                # Orden físico de las columnas en las tablas creadas.
                insert_columns = [
                    "snapshot_id", "source_file", *data_columns
                ]

                quoted_columns = ", ".join(
                    quote_identifier(column) for column in insert_columns
                )
                placeholders = ", ".join(
                    "?" for _ in insert_columns
                )

                update_columns = [
                    column for column in insert_columns
                    if column not in {"snapshot_id", "id"}
                ]

                update_clause = ", ".join(
                    f"{quote_identifier(column)} = excluded.{quote_identifier(column)}"
                    for column in update_columns
                )

                sql = (
                    f"INSERT INTO {quote_identifier(table)} "
                    f"({quoted_columns}) VALUES ({placeholders}) "
                    f"ON CONFLICT (snapshot_id, id) DO UPDATE SET "
                    f"{update_clause}"
                )

                batch = []
                seen_keys = set()

                for row in reader:
                    source_file = (row.get("_source_file") or "").strip()
                    record_id = (row.get(id_column) or "").strip()

                    if not source_file:
                        raise ValueError(
                            f"Fila {source_rows + 2}: _source_file vacío"
                        )

                    if not record_id:
                        raise ValueError(
                            f"Fila {source_rows + 2}: identificador vacío"
                        )

                    snapshot_id = snapshot_from_source(
                        source_file, config["prefix"]
                    )

                    key = (snapshot_id, record_id)
                    if key in seen_keys:
                        raise ValueError(
                            f"Clave duplicada en el archivo consolidado: {key}"
                        )
                    seen_keys.add(key)

                                        # Verificar que el snapshot esté registrado.
                                        
                    # Normalizar valores ausentes antes de cargar en Silver.
                    values = []

                    for column in data_columns:
                        value = row.get(column)

                        if value is not None:
                            value = value.strip()

                        # Convertir cadenas vacías y marcadores de ausencia en NULL.
                        if value == "":
                            value = None
                        elif column == "host_verifications" and value == "None":
                            value = None
                        elif column in {"name", "description"} and value is not None:
                            if value.lower() == "none":
                                value = None

                        values.append(value)

                    batch.append(
                        (
                            snapshot_id,
                            source_file,
                            *values,
                        )
                    )


                    source_rows += 1

                    if len(batch) >= BATCH_SIZE:
                        conn.executemany(sql, batch)
                        conn.commit()
                        loaded_rows += len(batch)
                        batch.clear()
                        print(
                            f"{dataset_name}: {loaded_rows:,} filas procesadas",
                            flush=True,
                        )

                if batch:
                    conn.executemany(sql, batch)
                    conn.commit()
                    loaded_rows += len(batch)

            # Verificar el número de filas por snapshot.
            counts = conn.execute(
                f"""
                SELECT snapshot_id, COUNT(*)
                FROM {quote_identifier(table)}
                GROUP BY snapshot_id
                ORDER BY snapshot_id
                """
            ).fetchall()

            conn.execute(
                """
                UPDATE etl_runs
                SET finished_at = ?, status = 'SUCCESS',
                    source_rows = ?, loaded_rows = ?, error_message = NULL
                WHERE run_id = ?
                """,
                (now_utc(), source_rows, loaded_rows, run_id),
            )
            conn.commit()

            print(f"\nCarga de {dataset_name} completada.")
            print(f"Filas leídas: {source_rows:,}")
            print(f"Filas procesadas: {loaded_rows:,}")
            print("Filas presentes en la tabla por snapshot:")
            for snapshot, count in counts:
                print(f"  {snapshot}: {count:,}")

        except Exception as error:
            conn.rollback()
            conn.execute(
                """
                UPDATE etl_runs
                SET finished_at = ?, status = 'FAILED',
                    source_rows = ?, loaded_rows = ?, error_message = ?
                WHERE run_id = ?
                """,
                (now_utc(), source_rows, loaded_rows, str(error), run_id),
            )
            conn.commit()
            raise


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "listings", "reviews", "all"
    }:
        print(
            "Uso: python data-lake/scripts/cargar_datos.py "
            "[listings|reviews|all]"
        )
        sys.exit(1)

    if not DB_FILE.is_file():
        raise FileNotFoundError(DB_FILE)

    selection = sys.argv[1]
    datasets = (
        list(DATASETS)
        if selection == "all"
        else [selection]
    )

    for dataset in datasets:
        load_dataset(dataset)


if __name__ == "__main__":
    main()
