
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

FILES = {
    "listings": BASE_DIR / "bronze" / "listings" / "unido" / "listings_unido.csv",
    "reviews": BASE_DIR / "bronze" / "reviews" / "unido" / "reviews_unido.csv",
}

for name, path in FILES.items():
    print(f"\n{'=' * 50}")
    print(f"VERIFICACIÓN: {name.upper()}")
    print("=" * 50)

    if not path.is_file():
        print(f"ERROR: No existe el archivo: {path}")
        continue

    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8",
    )

    print(f"Archivo: {path}")
    print(f"Filas: {len(df):,}")
    print(f"Columnas: {len(df.columns)}")

    duplicated_columns = df.columns[df.columns.duplicated()].tolist()
    print(f"Columnas duplicadas: {duplicated_columns}")

    if "_source_file" not in df.columns:
        print("ERROR: Falta la columna _source_file")
        continue

    print("\nFilas por archivo de origen:")
    print(df["_source_file"].value_counts().to_string())

    if "id" in df.columns:
        empty_ids = (df["id"].str.strip() == "").sum()
        unique_ids = df["id"].nunique()

        print(f"\nIDs vacíos: {empty_ids:,}")
        print(f"IDs únicos: {unique_ids:,}")
        print(f"Filas con ID repetido: {len(df) - unique_ids:,}")
    else:
        print("\nNo existe una columna llamada id.")

print("\nVerificación terminada.")
