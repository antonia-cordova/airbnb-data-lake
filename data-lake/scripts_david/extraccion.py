"""
Paso 1 - Extracción y unificación de Bronze.

Lee todos los archivos de un conjunto de datos (uno por snapshot) y los
unifica en un único DataFrame de pandas en memoria. Los archivos de Bronze
no se modifican ni se genera ningún archivo intermedio.

Todas las columnas se leen como texto: la conversión de tipos se hace
después, en transformacion.py.
"""

import json
import logging
from pathlib import Path

import pandas as pd

from config import BRONZE_DIR, Dataset

log = logging.getLogger(__name__)

# Columnas de procedencia que se agregan a cada fila.
COLUMNAS_PROCEDENCIA = ["snapshot_id", "source_file"]


def etiqueta_snapshot(archivo: Path) -> str:
    """Obtiene la etiqueta del snapshot: 'listings-MARCH.csv' -> 'MARCH'."""
    partes = archivo.stem.split("-", 1)
    if len(partes) != 2 or not partes[1]:
        raise ValueError(
            f"El archivo {archivo.name} no sigue el patrón <prefijo>-<ETIQUETA>"
        )
    return partes[1]


def listar_archivos(dataset: Dataset) -> list[Path]:
    """Devuelve los archivos de origen del conjunto de datos, ordenados."""
    carpeta = BRONZE_DIR / dataset.carpeta
    archivos = sorted(carpeta.glob(dataset.patron))
    if not archivos:
        raise FileNotFoundError(
            f"No hay archivos {dataset.patron} en {carpeta}"
        )
    return archivos


def leer_csv(archivo: Path) -> pd.DataFrame:
    """Lee un CSV de Inside Airbnb sin interpretar valores (todo como texto)."""
    return pd.read_csv(
        archivo,
        dtype="str",
        keep_default_na=False,  # las celdas vacías quedan como "" (se limpian después)
        encoding="utf-8-sig",
    )


def leer_geojson(archivo: Path) -> pd.DataFrame:
    """Convierte un GeoJSON en un DataFrame: una fila por entidad (barrio).

    Las propiedades pasan a columnas y la geometría se guarda como texto
    JSON, que en Silver se almacena como JSONB.
    """
    contenido = json.loads(archivo.read_text(encoding="utf-8"))
    filas = [
        {
            **entidad["properties"],
            "geometry_type": entidad["geometry"]["type"],
            "geometry": json.dumps(entidad["geometry"], ensure_ascii=False),
        }
        for entidad in contenido["features"]
    ]
    return pd.DataFrame(filas, dtype="str")


LECTORES = {
    "csv": leer_csv,
    "geojson": leer_geojson,
}


def unificar(dataset: Dataset) -> pd.DataFrame:
    """Une los snapshots de un conjunto de datos en un único DataFrame.

    A cada fila se le agregan snapshot_id (etiqueta del archivo) y
    source_file (nombre del archivo) para conservar su procedencia.
    """
    lector = LECTORES[dataset.formato]
    partes = []
    columnas_referencia = None

    for archivo in listar_archivos(dataset):
        df = lector(archivo)

        conflicto = set(COLUMNAS_PROCEDENCIA) & set(df.columns)
        if conflicto:
            raise ValueError(
                f"{archivo.name} ya contiene las columnas {sorted(conflicto)}"
            )

        # Avisar si un snapshot trae columnas distintas: pandas las alinea
        # y deja como nulas las que falten en cada archivo.
        if columnas_referencia is None:
            columnas_referencia = list(df.columns)
        elif set(df.columns) != set(columnas_referencia):
            log.warning(
                "%s tiene columnas distintas al primer archivo "
                "(sobran: %s, faltan: %s)",
                archivo.name,
                sorted(set(df.columns) - set(columnas_referencia)),
                sorted(set(columnas_referencia) - set(df.columns)),
            )

        df.insert(0, "snapshot_id", etiqueta_snapshot(archivo))
        df.insert(1, "source_file", archivo.name)
        partes.append(df)
        log.info("  %s: %s filas", archivo.name, f"{len(df):,}")

    unido = pd.concat(partes, ignore_index=True)
    log.info(
        "  Unificado: %s filas, %s columnas",
        f"{len(unido):,}",
        len(unido.columns),
    )
    return unido
