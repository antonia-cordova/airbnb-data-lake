import json
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_DIR / "data-lake" / "bronze"
DB_FILE = PROJECT_DIR / "data-lake" / "silver" / "airbnb_silver.db"

CSV_FILE = BRONZE_DIR / "neighbourhoods" / "unido" / "neighbourhoods_unido.csv"
GEOJSON_FILE = BRONZE_DIR / "geojson" / "unido" / "neighbourhoods_unido.geojson"


def main():
    import pandas as pd

    if not CSV_FILE.is_file():
        raise FileNotFoundError(f"No se encontró: {CSV_FILE}")
    if not GEOJSON_FILE.is_file():
        raise FileNotFoundError(f"No se encontró: {GEOJSON_FILE}")
    if not DB_FILE.is_file():
        raise FileNotFoundError(f"No se encontró: {DB_FILE}")

    df = pd.read_csv(CSV_FILE, dtype=str, keep_default_na=False)

    required_columns = {
        "neighbourhood",
        "neighbourhood_group",
        "_source_file",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Faltan columnas en el CSV: {sorted(missing_columns)}"
        )

    # Elegir un registro por barrio
    df = df[["neighbourhood", "neighbourhood_group", "_source_file"]].copy()
    df["neighbourhood"] = df["neighbourhood"].str.strip()
    df["neighbourhood_group"] = df["neighbourhood_group"].str.strip()
    df = df[df["neighbourhood"] != ""]

    # Validar que cada barrio tenga un solo valor de grupo no vacío,
    # cuando ese valor exista.
    for name, group in df.groupby("neighbourhood"):
        values = set(group["neighbourhood_group"]) - {""}
        if len(values) > 1:
            raise ValueError(
                f"El barrio {name!r} tiene grupos inconsistentes: {values}"
            )

    canonical = (
        df.sort_values("_source_file")
        .drop_duplicates(subset=["neighbourhood"])
    )

    with GEOJSON_FILE.open(encoding="utf-8") as f:
        geojson = json.load(f)

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("El GeoJSON no es una FeatureCollection.")

    geometry_by_name = {}
    geometry_source_by_name = {}

    for feature in geojson.get("features", []):
        properties = feature.get("properties") or {}
        name = str(properties.get("neighbourhood", "")).strip()
        geometry = feature.get("geometry")
        source = properties.get("_source_file", "")

        if not name or not isinstance(geometry, dict):
            raise ValueError(
                f"Feature sin nombre o geometría válida: {properties}"
            )

        serialized = json.dumps(
            geometry, ensure_ascii=False, separators=(",", ":")
        )

        if name in geometry_by_name and geometry_by_name[name] != serialized:
            raise ValueError(
                f"Geometrías diferentes para {name!r}; no se cargará."
            )

        geometry_by_name[name] = serialized
        if name not in geometry_source_by_name:
            geometry_source_by_name[name] = source

    csv_names = set(canonical["neighbourhood"])
    geo_names = set(geometry_by_name)

    if csv_names != geo_names:
        raise ValueError(
            f"Los barrios no coinciden entre CSV y GeoJSON. "
            f"Solo CSV: {sorted(csv_names - geo_names)}; "
            f"solo GeoJSON: {sorted(geo_names - csv_names)}"
        )

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # registrar snapshots que identifican los archivos de origen
        snapshots = [
            ("MARCH", "MARCH", "Snapshot de origen MARCH"),
            ("JUNE", "JUNE", "Snapshot de origen JUNE"),
            ("SEP", "SEP", "Snapshot de origen SEP"),
        ]
        conn.executemany(
            """
            INSERT INTO source_snapshots
                (snapshot_id, source_label, description)
            VALUES (?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                source_label = excluded.source_label,
                description = excluded.description
            """,
            snapshots,
        )

        names = sorted(csv_names)
        ids = {name: i + 1 for i, name in enumerate(names)}

        conn.executemany(
            """
            INSERT INTO neighbourhoods
                (neighbourhood_id, neighbourhood_name, neighbourhood_group)
            VALUES (?, ?, ?)
            ON CONFLICT(neighbourhood_name) DO UPDATE SET
                neighbourhood_group = excluded.neighbourhood_group
            """,
            [
                (
                    ids[row["neighbourhood"]],
                    row["neighbourhood"],
                    row["neighbourhood_group"] or None,
                )
                for _, row in canonical.iterrows()
            ],
        )

        # Leer IDs existentes para respetar la clave de la tabla
        existing_ids = dict(
            conn.execute(
                "SELECT neighbourhood_name, neighbourhood_id FROM neighbourhoods"
            ).fetchall()
        )

        conn.executemany(
            """
            INSERT INTO neighbourhood_geometries
                (neighbourhood_id, geometry_type, geometry_json, source_file)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(neighbourhood_id) DO UPDATE SET
                geometry_type = excluded.geometry_type,
                geometry_json = excluded.geometry_json,
                source_file = excluded.source_file
            """,
            [
                (
                    existing_ids[name],
                    json.loads(geometry_by_name[name])["type"],
                    geometry_by_name[name],
                    geometry_source_by_name[name],
                )
                for name in sorted(geo_names)
            ],
        )

        neighbourhood_count = conn.execute(
            "SELECT COUNT(*) FROM neighbourhoods"
        ).fetchone()[0]
        geometry_count = conn.execute(
            "SELECT COUNT(*) FROM neighbourhood_geometries"
        ).fetchone()[0]
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM source_snapshots"
        ).fetchone()[0]

    print("Carga de barrios completada correctamente.")
    print(f"Barrios en CSV: {len(csv_names)}")
    print(f"Geometrías canónicas: {len(geo_names)}")
    print(f"Snapshots registrados: {snapshot_count}")
    print(f"Filas en neighbourhoods: {neighbourhood_count}")
    print(f"Filas en neighbourhood_geometries: {geometry_count}")


if __name__ == "__main__":
    main()
