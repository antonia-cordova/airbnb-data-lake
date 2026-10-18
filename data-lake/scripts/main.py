"""
Punto de entrada único del ETL Bronze -> Silver (PostgreSQL).

Para cada conjunto de datos registrado en config.DATASETS:

    1. Unifica sus snapshots de Bronze en un DataFrame (sin escribir archivos).
    2. Audita los vacíos de Bronze (reporte).
    3. Limpia y tipa los datos: vacíos -> NULL, t/f -> BOOLEAN,
       números sin '$' ni ',', fechas -> DATE, JSON -> JSONB.
    4. Recrea y carga la tabla silver_<nombre> en PostgreSQL.
    5. Audita los NULL en Silver y valida los conteos contra Bronze.

Al terminar, exporta el esquema real de Silver a
sql/create_silver_postgres.sql (pg_dump --schema-only).

Uso (desde la raíz del repositorio, con PostgreSQL levantado):

    docker compose up -d
    python data-lake/scripts/main.py                     # todo
    python data-lake/scripts/main.py listings reviews    # solo algunos
    python data-lake/scripts/main.py --sin-reportes      # solo ETL
"""

import argparse
import gc
import logging
import sys
import time

import pandas as pd
from sqlalchemy import Engine

import carga
import esquema
import reportes
from config import DATASETS, Dataset
from extraccion import unificar
from transformacion import transformar, validar_clave

log = logging.getLogger("etl")


def procesar_dataset(motor: Engine, dataset: Dataset,
                     con_reportes: bool) -> pd.DataFrame:
    """Ejecuta el ETL completo de un conjunto de datos.

    Devuelve la comparación de conteos Bronze/Silver para el reporte final.
    """
    log.info("=" * 60)
    log.info("%s -> %s", dataset.nombre.upper(), dataset.tabla)
    log.info("=" * 60)

    # 1. Extracción y unificación
    log.info("[1/5] Unificando snapshots de Bronze")
    df = unificar(dataset)
    filas_bronze = df.groupby("snapshot_id").size()

    # 2. Auditoría de Bronze (antes de limpiar)
    if con_reportes:
        log.info("[2/5] Auditando vacíos en Bronze")
        reportes.auditar_nulos_bronze(df, dataset)

    run_id = carga.registrar_inicio(motor, dataset, len(df))
    try:
        # 3. Limpieza y tipado
        log.info("[3/5] Limpiando y tipando datos")
        tipos = transformar(df)
        validar_clave(df, dataset.clave)

        # 4. Carga en PostgreSQL
        log.info("[4/5] Cargando en PostgreSQL")
        filas_cargadas = carga.cargar_tabla(motor, df, tipos, dataset)
        carga.registrar_fin(motor, run_id, "SUCCESS", filas_cargadas)
    except Exception as error:
        carga.registrar_fin(motor, run_id, "FAILED", error=str(error))
        raise
    finally:
        # Liberar la memoria del DataFrame antes del siguiente conjunto.
        columnas = list(df.columns)
        del df
        gc.collect()

    # 5. Auditoría de Silver y validación
    log.info("[5/5] Validando la carga")
    if con_reportes:
        reportes.reportar_tipos(tipos, dataset)
        reportes.auditar_nulos_silver(motor, dataset, columnas)
    return reportes.validar_carga(motor, dataset, filas_bronze)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ETL Bronze -> Silver (PostgreSQL) de Inside Airbnb CDMX."
    )
    parser.add_argument(
        "datasets",
        nargs="*",
        choices=list(DATASETS),
        default=list(DATASETS),
        help="Conjuntos a procesar (por defecto, todos).",
    )
    parser.add_argument(
        "--sin-reportes",
        action="store_true",
        help="No generar los reportes de nulos ni de tipos.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    inicio = time.perf_counter()
    motor = carga.crear_motor()
    carga.asegurar_tabla_etl_runs(motor)

    validaciones = []
    for nombre in args.datasets:
        validaciones.append(
            procesar_dataset(motor, DATASETS[nombre], not args.sin_reportes)
        )

    reportes.guardar_validacion(validaciones)
    resultado = pd.concat(validaciones, ignore_index=True)

    # El esquema es documentación: si no se puede exportar, se avisa pero
    # la carga, que ya terminó bien, no se da por fallida.
    log.info("=" * 60)
    log.info("Exportando el esquema de Silver")
    try:
        esquema.exportar_esquema()
    except RuntimeError as error:
        log.warning("%s", error)

    log.info("=" * 60)
    log.info("RESUMEN\n%s", resultado.to_string(index=False))
    log.info("Tiempo total: %.1f s", time.perf_counter() - inicio)

    if not resultado["matches"].all():
        log.error("Hay diferencias entre Bronze y Silver.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
