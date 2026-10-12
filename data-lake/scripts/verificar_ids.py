
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

DATASETS = {
    "listings": {
        "folder": "listings",
        "files": [
            "listings-MARCH.csv",
            "listings-JUNE.csv",
            "listings-SEP.csv",
        ],
        "id_column": "id",
    },
    "reviews": {
        "folder": "reviews",
        "files": [
            "reviews-MARCH.csv",
            "reviews-JUNE.csv",
            "reviews-SEP.csv",
        ],
        "id_column": "id",
    },
}

for dataset, config in DATASETS.items():
    print(f"\n{'=' * 55}")
    print(f"VERIFICACIÓN DE IDs: {dataset.upper()}")
    print("=" * 55)

    folder = BASE_DIR / "bronze" / config["folder"]
    id_column = config["id_column"]

    for filename in config["files"]:
        path = folder / filename

        if not path.is_file():
            print(f"\nNo encontrado: {path}")
            continue

        df = pd.read_csv(
            path,
            usecols=[id_column],
            dtype=str,
            keep_default_na=False,
            encoding="utf-8",
        )

        ids = df[id_column].str.strip()

        empty_ids = (ids == "").sum()
        nonempty_ids = ids[ids != ""]

        duplicated_rows = nonempty_ids.duplicated().sum()
        unique_ids = nonempty_ids.nunique()

        print(f"\nArchivo: {filename}")
        print(f"Filas: {len(df):,}")
        print(f"IDs únicos no vacíos: {unique_ids:,}")
        print(f"IDs vacíos: {empty_ids:,}")
        print(f"Filas con ID repetido dentro del archivo: {duplicated_rows:,}")
