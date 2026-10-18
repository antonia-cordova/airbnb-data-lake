"""
Paso 7 - Reportes de calidad (todos los CSV se escriben con pandas).

Genera en data-lake/reportes/:

    bronze/<dataset>/           (p. ej. bronze/listings/)
        nulos_por_snapshot.csv  Vacíos por columna en Bronze, antes de limpiar.
        nulos_resumen.csv
    silver/<tabla>/             (p. ej. silver/silver_listings/)
        nulos_por_snapshot.csv  NULL por columna en PostgreSQL, después de
        nulos_resumen.csv       cargar. Al compararlos con los de Bronze se
                                ve el efecto de la limpieza.
        tipos.csv               Tipo de PostgreSQL asignado a cada columna.
    validacion_carga.csv        Filas por snapshot en Bronze frente a Silver,
                                para todas las tablas.

Los conteos de Silver se calculan con SQL dentro de PostgreSQL y solo el
resultado se trae a pandas, para no volver a cargar millones de filas en
memoria.
"""

import logging
from pathlib import Path

import pandas as pd
from psycopg import sql
from sqlalchemy import Engine

from config import REPORT_DIR, Dataset
from extraccion import COLUMNAS_PROCEDENCIA

log = logging.getLogger(__name__)


def _carpeta_bronze(dataset: Dataset) -> Path:
    """Carpeta de reportes de Bronze del conjunto: bronze/<dataset>/."""
    return Path("bronze") / dataset.nombre


def _carpeta_silver(dataset: Dataset) -> Path:
    """Carpeta de reportes de Silver de la tabla: silver/<tabla>/."""
    return Path("silver") / dataset.tabla


def _guardar(df: pd.DataFrame, ruta_relativa: Path) -> None:
    """Escribe el CSV en REPORT_DIR/<ruta_relativa>, creando las carpetas."""
    ruta = REPORT_DIR / ruta_relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8")
    log.info("  Reporte: %s", ruta.relative_to(REPORT_DIR.parent.parent))


def _tablas_de_nulos(conteos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Arma los reportes de nulos a partir de un conteo por snapshot.

    `conteos` tiene una fila por snapshot (índice), una columna total_rows y
    una columna por cada columna de datos con su cantidad de nulos.
    """
    totales = conteos["total_rows"]
    por_snapshot = (
        conteos.drop(columns="total_rows")
        .rename_axis("snapshot")
        .reset_index()
        .melt(id_vars="snapshot", var_name="column", value_name="null_count")
    )
    por_snapshot.insert(2, "total_rows", por_snapshot["snapshot"].map(totales))
    por_snapshot["null_percent"] = (
        100 * por_snapshot["null_count"] / por_snapshot["total_rows"]
    ).round(4)

    resumen = por_snapshot.groupby("column", sort=False).agg(
        total_rows=("total_rows", "sum"),
        null_count=("null_count", "sum"),
        max_snapshot_null_percent=("null_percent", "max"),
    )
    resumen.insert(
        2, "null_percent",
        (100 * resumen["null_count"] / resumen["total_rows"]).round(4),
    )
    resumen = resumen.reset_index().sort_values(
        "null_percent", ascending=False, kind="stable"
    )
    return por_snapshot, resumen


def auditar_nulos_bronze(df: pd.DataFrame, dataset: Dataset) -> None:
    """Cuenta celdas vacías por columna en los datos crudos de Bronze."""
    columnas = [c for c in df.columns if c not in COLUMNAS_PROCEDENCIA]
    vacios = df[columnas].apply(lambda s: s.isna() | s.str.strip().eq(""))
    conteos = vacios.groupby(df["snapshot_id"]).sum()
    conteos.insert(0, "total_rows", df.groupby("snapshot_id").size())

    por_snapshot, resumen = _tablas_de_nulos(conteos)
    carpeta = _carpeta_bronze(dataset)
    _guardar(por_snapshot, carpeta / "nulos_por_snapshot.csv")
    _guardar(resumen, carpeta / "nulos_resumen.csv")


def auditar_nulos_silver(motor: Engine, dataset: Dataset,
                         columnas: list[str]) -> None:
    """Cuenta NULL por columna en la tabla de Silver, agrupado por snapshot."""
    columnas = [c for c in columnas if c not in COLUMNAS_PROCEDENCIA]
    conteos_sql = [
        sql.SQL("COUNT(*) - COUNT({col}) AS {col}").format(col=sql.Identifier(c))
        for c in columnas
    ]
    consulta = sql.SQL(
        "SELECT snapshot_id, COUNT(*) AS total_rows, {} FROM {} "
        "GROUP BY snapshot_id ORDER BY snapshot_id"
    ).format(sql.SQL(", ").join(conteos_sql), sql.Identifier(dataset.tabla))

    conexion = motor.raw_connection()
    try:
        texto = consulta.as_string(conexion.driver_connection)
    finally:
        conexion.close()

    conteos = pd.read_sql(texto, motor).set_index("snapshot_id")
    por_snapshot, resumen = _tablas_de_nulos(conteos)
    carpeta = _carpeta_silver(dataset)
    _guardar(por_snapshot, carpeta / "nulos_por_snapshot.csv")
    _guardar(resumen, carpeta / "nulos_resumen.csv")


def reportar_tipos(tipos: dict[str, str], dataset: Dataset) -> None:
    """Guarda el tipo de PostgreSQL asignado a cada columna."""
    reporte = pd.DataFrame(
        {"column": list(tipos), "postgres_type": list(tipos.values())}
    )
    _guardar(reporte, _carpeta_silver(dataset) / "tipos.csv")


def validar_carga(motor: Engine, dataset: Dataset,
                  filas_bronze: pd.Series) -> pd.DataFrame:
    """Compara las filas por snapshot entre Bronze y la tabla de Silver."""
    consulta = (
        f'SELECT snapshot_id, COUNT(*) AS silver_rows FROM "{dataset.tabla}" '
        "GROUP BY snapshot_id"
    )
    filas_silver = pd.read_sql(consulta, motor).set_index("snapshot_id")

    comparacion = (
        filas_bronze.rename("bronze_rows").to_frame()
        .join(filas_silver, how="outer")
        .fillna(0)
        .astype("int64")
        .rename_axis("snapshot")
        .reset_index()
    )
    comparacion.insert(0, "table", dataset.tabla)
    comparacion["matches"] = comparacion["bronze_rows"] == comparacion["silver_rows"]

    if not comparacion["matches"].all():
        log.warning("  Conteos distintos entre Bronze y Silver en %s", dataset.tabla)
    return comparacion


def guardar_validacion(validaciones: list[pd.DataFrame]) -> None:
    """Guarda en un único CSV la validación de todos los conjuntos cargados."""
    if validaciones:
        _guardar(
            pd.concat(validaciones, ignore_index=True),
            Path("validacion_carga.csv"),
        )
