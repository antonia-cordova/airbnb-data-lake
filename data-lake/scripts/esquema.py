"""
Paso 8 - Exportación del esquema real de Silver.

Al final de cada ejecución del ETL se ejecuta pg_dump en modo
--schema-only sobre las tablas silver_* y el resultado se guarda en
sql/create_silver_postgres.sql. Así queda versionado el esquema que
realmente existe en PostgreSQL (tablas, tipos inferidos, claves primarias
y comentarios), aunque las tablas se generen dinámicamente.

El archivo es solo documentación: el ETL no lo lee.

pg_dump se busca en este orden y se usa el primero que funcione:
1. pg_dump instalado en el equipo.
2. pg_dump dentro del contenedor de docker compose (servicio "postgres"),
   que siempre tiene la misma versión que el servidor.
"""

import logging
import os
import shutil
import subprocess

from config import ARCHIVO_ESQUEMA, PROJECT_DIR

log = logging.getLogger(__name__)

# pg_dump (17.6+) agrega líneas \restrict <llave>. Con una llave aleatoria el
# archivo cambiaría en cada ejecución aunque el esquema fuera el mismo.
LLAVE_RESTRICT = "silverschema"

OPCIONES_PG_DUMP = [
    "--schema-only",          # sin datos
    "--no-owner",             # sin ALTER ... OWNER (depende del usuario)
    "--no-privileges",        # sin GRANT / REVOKE
    "--table=silver_*",       # solo las tablas de la capa Silver
    f"--restrict-key={LLAVE_RESTRICT}",
]

ENCABEZADO = (
    "-- Esquema real de la capa Silver en PostgreSQL.\n"
    "-- Generado automáticamente por data-lake/scripts/esquema.py\n"
    "-- al final de cada ejecución de main.py. No editar a mano.\n\n"
)


def _comandos_candidatos() -> list[tuple[str, list[str]]]:
    """Devuelve los comandos de pg_dump disponibles, en orden de preferencia."""
    usuario = os.getenv("PGUSER")
    base_datos = os.getenv("PGDATABASE")
    candidatos = []

    if shutil.which("pg_dump"):
        candidatos.append((
            "pg_dump local",
            [
                "pg_dump",
                f"--host={os.getenv('PGHOST', 'localhost')}",
                f"--port={os.getenv('PGPORT', '5433')}",
                f"--username={usuario}",
                f"--dbname={base_datos}",
            ],
        ))

    if shutil.which("docker"):
        candidatos.append((
            "pg_dump del contenedor",
            [
                "docker", "compose", "exec", "-T", "postgres",
                "pg_dump", f"--username={usuario}", f"--dbname={base_datos}",
            ],
        ))

    return candidatos


def exportar_esquema() -> None:
    """Ejecuta pg_dump y escribe el esquema en sql/create_silver_postgres.sql."""
    # PGPASSWORD evita que pg_dump pida la contraseña de forma interactiva.
    entorno = {**os.environ, "PGPASSWORD": os.getenv("PGPASSWORD", "")}
    errores = []

    for nombre, comando in _comandos_candidatos():
        resultado = subprocess.run(
            comando + OPCIONES_PG_DUMP,
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,  # docker compose busca aquí docker-compose.yml
            env=entorno,
            check=False,
        )
        if resultado.returncode == 0:
            ARCHIVO_ESQUEMA.parent.mkdir(parents=True, exist_ok=True)
            ARCHIVO_ESQUEMA.write_text(
                ENCABEZADO + resultado.stdout, encoding="utf-8"
            )
            log.info(
                "  Esquema exportado con %s: %s",
                nombre,
                ARCHIVO_ESQUEMA.relative_to(PROJECT_DIR),
            )
            return

        # Por ejemplo, un pg_dump local más antiguo que el servidor.
        errores.append(f"{nombre}: {resultado.stderr.strip()}")

    if not errores:
        errores.append("no se encontró pg_dump ni docker en el sistema")
    raise RuntimeError(
        "No se pudo exportar el esquema.\n" + "\n".join(errores)
    )
