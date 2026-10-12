
from pathlib import Path
import argparse
import pandas as pd


# Directorio data-lake/
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración de los conjuntos de datos
DATASETS = {
    "listings": {
        "folder": "listings",
        "files": [
            "listings-MARCH.csv",
            "listings-JUNE.csv",
            "listings-SEP.csv",
        ],
        "output": "listings_unido.csv",
    },
    "reviews": {
        "folder": "reviews",
        "files": [
            "reviews-MARCH.csv",
            "reviews-JUNE.csv",
            "reviews-SEP.csv",
        ],
        "output": "reviews_unido.csv",
    },

    "neighbourhoods": {
        "folder": "neighbourhoods",
        "files": [
            "neighbourhoods-MARCH.csv",
            "neighbourhoods-JUNE.csv",
            "neighbourhoods-SEP.csv",
        ],
        "output": "neighbourhoods_unido.csv",
    }
}


def unificar_csv(dataset_name):
    """Unifica las versiones de un conjunto de datos CSV."""

    config = DATASETS[dataset_name]

    bronze_dir = BASE_DIR / "bronze" / config["folder"]
    output_dir = bronze_dir / "unido"
    output_file = output_dir / config["output"]

    files = [
        bronze_dir / filename
        for filename in config["files"]
    ]

    # Verificar que existan todos los archivos originales
    for file in files:
        if not file.is_file():
            raise FileNotFoundError(
                f"No se encontró el archivo: {file}"
            )

    dataframes = []
    reference_columns = None

    # Leer y validar cada CSV
    for file in files:
        print(f"\nLeyendo: {file.name}")

        df = pd.read_csv(
            file,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8",
        )

        # Verificar que no existan nombres de columnas duplicados
        if df.columns.duplicated().any():
            raise ValueError(
                f"Hay nombres de columnas duplicados en {file.name}"
            )

        # Establecer y validar el esquema
        if reference_columns is None:
            reference_columns = list(df.columns)

        elif set(df.columns) != set(reference_columns):
            missing = set(reference_columns) - set(df.columns)
            extra = set(df.columns) - set(reference_columns)

            raise ValueError(
                f"Las columnas no coinciden en {file.name}.\n"
                f"Faltantes: {missing}\n"
                f"Adicionales: {extra}"
            )

        # Conservar el mismo orden de columnas
        df = df[reference_columns]

        # Registrar la procedencia de cada registro
        df["_source_file"] = file.name

        dataframes.append(df)
        print(f"Filas leídas: {len(df):,}")

    # Concatenar los registros verticalmente
    combined = pd.concat(dataframes, ignore_index=True)

    # Crear la carpeta de salida si no existe
    output_dir.mkdir(parents=True, exist_ok=True)

    # Guardar el resultado
    combined.to_csv(
        output_file,
        index=False,
        encoding="utf-8",
    )

    # Verificar que se pueda leer el archivo generado
    verification = pd.read_csv(
        output_file,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8",
    )

    if len(verification) != len(combined):
        raise RuntimeError(
            "La verificación falló: las filas no coinciden."
        )

    print("\nUnificación completada.")
    print(f"Conjunto de datos: {dataset_name}")
    print(f"Archivos integrados: {len(files)}")
    print(f"Filas totales: {len(verification):,}")
    print(f"Columnas totales: {len(verification.columns)}")
    print("\nRegistros por archivo de origen:")
    print(verification["_source_file"].value_counts().to_string())
    print(f"\nArchivo generado: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Unifica versiones CSV de Inside Airbnb."
    )

    parser.add_argument(
        "dataset",
        choices=DATASETS.keys(),
        help="Conjunto de datos que se desea unificar.",
    )

    args = parser.parse_args()

    unificar_csv(args.dataset)
