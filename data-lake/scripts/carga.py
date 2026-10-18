"""
Paso 6 - Carga de los DataFrames limpios en PostgreSQL (capa Silver).

Cada tabla se recarga completa dentro de una sola transacción:
DROP TABLE -> CREATE TABLE (con tipos y clave primaria) -> COPY.
Si algo falla, PostgreSQL revierte todo y la tabla anterior queda intacta.
Así la carga es repetible: volver a ejecutar el ETL (por ejemplo, tras
agregar un snapshot nuevo en Bronze) deja Silver igual a Bronze sin duplicar.

Cada ejecución queda registrada en la tabla silver_etl_runs.
"""

import logging
from datetime import datetime, timezone

import pandas as pd
from psycopg import sql
from sqlalchemy import Engine, create_engine, text

from config import TABLA_ETL_RUNS, TAM_LOTE_COPY, Dataset, url_postgres

log = logging.getLogger(__name__)

# Marca de NULL en el CSV que se envía por COPY.
MARCA_NULO = r"\N"


def crear_motor() -> Engine:
    """Crea el motor de SQLAlchemy y verifica que PostgreSQL responda."""
    motor = create_engine(url_postgres())
    try:
        with motor.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except Exception as error:
        raise ConnectionError(
            "No se pudo conectar a PostgreSQL. ¿Está levantado el contenedor? "
            "Ejecuta `docker compose up -d` en la raíz del repositorio."
        ) from error
    return motor


# ---------------------------------------------------------------------------
# Bitácora de ejecuciones
# ---------------------------------------------------------------------------
def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def asegurar_tabla_etl_runs(motor: Engine) -> None:
    """Crea la tabla de bitácora si no existe (no se borra entre ejecuciones)."""
    with motor.begin() as conexion:
        conexion.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLA_ETL_RUNS} (
                run_id        BIGSERIAL PRIMARY KEY,
                dataset_name  TEXT NOT NULL,
                target_table  TEXT NOT NULL,
                started_at    TIMESTAMPTZ NOT NULL,
                finished_at   TIMESTAMPTZ,
                status        TEXT NOT NULL
                    CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
                source_rows   BIGINT,
                loaded_rows   BIGINT,
                error_message TEXT
            )
        """))
        conexion.execute(text(
            f"COMMENT ON TABLE {TABLA_ETL_RUNS} IS "
            "'Capa Silver: bitácora de ejecuciones del ETL.'"
        ))


def registrar_inicio(motor: Engine, dataset: Dataset, filas_origen: int) -> int:
    """Registra una ejecución en estado RUNNING y devuelve su run_id."""
    with motor.begin() as conexion:
        return conexion.execute(
            text(f"""
                INSERT INTO {TABLA_ETL_RUNS}
                    (dataset_name, target_table, started_at, status, source_rows)
                VALUES (:dataset, :tabla, :inicio, 'RUNNING', :filas)
                RETURNING run_id
            """),
            {
                "dataset": dataset.nombre,
                "tabla": dataset.tabla,
                "inicio": _ahora(),
                "filas": filas_origen,
            },
        ).scalar_one()


def registrar_fin(
    motor: Engine,
    run_id: int,
    estado: str,
    filas_cargadas: int | None = None,
    error: str | None = None,
) -> None:
    """Cierra una ejecución con estado SUCCESS o FAILED."""
    with motor.begin() as conexion:
        conexion.execute(
            text(f"""
                UPDATE {TABLA_ETL_RUNS}
                SET finished_at = :fin, status = :estado,
                    loaded_rows = :filas, error_message = :error
                WHERE run_id = :run_id
            """),
            {
                "fin": _ahora(),
                "estado": estado,
                "filas": filas_cargadas,
                "error": error,
                "run_id": run_id,
            },
        )


# ---------------------------------------------------------------------------
# Carga de tablas
# ---------------------------------------------------------------------------
def _sql_crear_tabla(dataset: Dataset, tipos: dict[str, str]) -> sql.Composed:
    """Genera el CREATE TABLE con los tipos inferidos y la clave primaria."""
    definiciones = []
    for columna, tipo in tipos.items():
        restriccion = " NOT NULL" if columna in dataset.clave else ""
        definiciones.append(
            sql.SQL("{} {}{}").format(
                sql.Identifier(columna), sql.SQL(tipo), sql.SQL(restriccion)
            )
        )
    definiciones.append(
        sql.SQL("PRIMARY KEY ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, dataset.clave))
        )
    )
    return sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(dataset.tabla), sql.SQL(", ").join(definiciones)
    )


def _bloques_csv(df: pd.DataFrame):
    """Convierte el DataFrame en bloques de texto CSV para el COPY."""
    for inicio in range(0, len(df), TAM_LOTE_COPY):
        yield df.iloc[inicio:inicio + TAM_LOTE_COPY].to_csv(
            header=False,
            index=False,
            na_rep=MARCA_NULO,
            date_format="%Y-%m-%d",
        )


def cargar_tabla(motor: Engine, df: pd.DataFrame, tipos: dict[str, str],
                 dataset: Dataset) -> int:
    """Recrea la tabla de Silver y carga el DataFrame con COPY.

    Devuelve el número de filas presentes en la tabla tras la carga.
    """
    columnas = sql.SQL(", ").join(map(sql.Identifier, df.columns))
    copy = sql.SQL(
        "COPY {} ({}) FROM STDIN WITH (FORMAT csv, NULL {})"
    ).format(sql.Identifier(dataset.tabla), columnas, sql.Literal(MARCA_NULO))

    conexion = motor.raw_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP TABLE IF EXISTS {}").format(
                    sql.Identifier(dataset.tabla)
                )
            )
            cursor.execute(_sql_crear_tabla(dataset, tipos))
            cursor.execute(
                sql.SQL("COMMENT ON TABLE {} IS {}").format(
                    sql.Identifier(dataset.tabla),
                    sql.Literal(dataset.descripcion),
                )
            )

            with cursor.copy(copy) as destino:
                enviadas = 0
                for bloque in _bloques_csv(df):
                    destino.write(bloque)
                    enviadas = min(enviadas + TAM_LOTE_COPY, len(df))
                    if len(df) > TAM_LOTE_COPY:
                        log.info("  COPY %s: %s / %s filas", dataset.tabla,
                                 f"{enviadas:,}", f"{len(df):,}")

            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(
                    sql.Identifier(dataset.tabla)
                )
            )
            filas = cursor.fetchone()[0]

        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    log.info("  Tabla %s cargada: %s filas", dataset.tabla, f"{filas:,}")
    return filas
