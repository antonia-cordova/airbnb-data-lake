"""
Configuración central del ETL Bronze -> Silver (PostgreSQL).

Todo lo que define QUÉ se procesa vive aquí, para que el resto de los
módulos sea genérico:

- Para agregar un nuevo snapshot basta con dejar el archivo en su carpeta de
  Bronze siguiendo el patrón <prefijo>-<ETIQUETA>.<extensión>
  (por ejemplo, listings-DEC.csv). La etiqueta se usa como snapshot_id.
- Para agregar un nuevo conjunto de datos basta con registrarlo en DATASETS.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_DIR / "data-lake" / "bronze"
REPORT_DIR = PROJECT_DIR / "data-lake" / "reportes"
# Esquema real de Silver exportado con pg_dump tras cada carga.
ARCHIVO_ESQUEMA = PROJECT_DIR / "sql" / "create_silver_postgres.sql"

# Credenciales de PostgreSQL (archivo .env en la raíz del repositorio).
load_dotenv(PROJECT_DIR / ".env")


# ---------------------------------------------------------------------------
# Conjuntos de datos
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Dataset:
    nombre: str                # nombre lógico (se usa en la línea de comandos)
    carpeta: str               # subcarpeta dentro de bronze/
    patron: str                # glob de los archivos de origen
    formato: str               # "csv" o "geojson"
    tabla: str                 # tabla destino en Silver
    clave: tuple[str, ...]     # clave primaria (siempre incluye snapshot_id)
    descripcion: str           # comentario de la tabla en PostgreSQL


DATASETS = {
    dataset.nombre: dataset
    for dataset in [
        Dataset(
            nombre="listings",
            carpeta="listings",
            patron="listings-*.csv",
            formato="csv",
            tabla="silver_listings",
            clave=("snapshot_id", "id"),
            descripcion="Capa Silver: alojamientos por snapshot.",
        ),
        Dataset(
            nombre="reviews",
            carpeta="reviews",
            patron="reviews-*.csv",
            formato="csv",
            tabla="silver_reviews",
            clave=("snapshot_id", "id"),
            descripcion="Capa Silver: reseñas por snapshot.",
        ),
        Dataset(
            nombre="neighbourhoods",
            carpeta="neighbourhoods",
            patron="neighbourhoods-*.csv",
            formato="csv",
            tabla="silver_neighbourhoods",
            clave=("snapshot_id", "neighbourhood"),
            descripcion="Capa Silver: catálogo de barrios por snapshot.",
        ),
        Dataset(
            nombre="geojson",
            carpeta="geojson",
            patron="neighbourhoods-*.geojson",
            formato="geojson",
            tabla="silver_neighbourhood_geometries",
            clave=("snapshot_id", "neighbourhood"),
            descripcion="Capa Silver: geometrías de barrios por snapshot.",
        ),
    ]
}

# Tabla de bitácora de ejecuciones del ETL.
TABLA_ETL_RUNS = "silver_etl_runs"


# ---------------------------------------------------------------------------
# Reglas de limpieza
# ---------------------------------------------------------------------------
# Textos que indican ausencia de dato, por columna (sin distinguir
# mayúsculas). No se aplican a todas las columnas porque, por ejemplo, en
# host_name y reviewer_name "Nan" o "Na" son nombres reales.
MARCADORES_NULOS = {
    "host_verifications": {"none"},
    "name": {"none"},
    "description": {"none"},
}

# Filas que se envían a PostgreSQL en cada bloque del COPY.
TAM_LOTE_COPY = 100_000


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def url_postgres():
    """Construye la URL de conexión de SQLAlchemy a partir del .env."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5433")),
        database=os.getenv("PGDATABASE"),
    )
