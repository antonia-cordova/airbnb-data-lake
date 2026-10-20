"""
Pasos 2 a 5 - Limpieza y tipado de los datos unificados.

1. Vacíos -> NULL: celdas vacías o con solo espacios, y los marcadores de
   ausencia configurados por columna (config.MARCADORES_NULOS).
2. Inferencia de tipo por columna, mirando todos sus valores no nulos:
   - BOOLEAN : solo contiene 't' / 'f'.
   - DATE    : solo contiene fechas AAAA-MM-DD (se guardan como DATE de
               PostgreSQL; el formato de salida se elige al consultar,
               p. ej. to_char(fecha, 'DD-MM-YYYY')).
   - BIGINT  : enteros (tras quitar '$', ',', '%' y espacios) que caben en 64 bits.
   - NUMERIC : números con decimales (mismo criterio de limpieza).
   - JSONB   : listas u objetos JSON válidos (amenities, price_quote_raw, geometry).
   - TEXT    : todo lo demás.
3. Conversión de cada columna a su tipo.

La inferencia es automática, así que nuevas columnas o snapshots no
requieren cambiar el código. Las columnas se convierten en el mismo
DataFrame (in place) para no duplicar la memoria con las reseñas.
"""

import json
import logging

import pandas as pd

from config import MARCADORES_NULOS
from extraccion import COLUMNAS_PROCEDENCIA

log = logging.getLogger(__name__)

PATRON_FECHA = r"\d{4}-\d{2}-\d{2}"
PATRON_ENTERO = r"-?\d+"
PATRON_DECIMAL = r"-?\d+(?:\.\d+)?"
CARACTERES_NO_NUMERICOS = r"[$,%\s]"
VALORES_BOOLEANOS = {"t": True, "f": False}
MAX_BIGINT = 2**63 - 1

# Antes de revisar millones de valores se prueba con una muestra: si la
# muestra ya no cumple, se descarta el tipo sin recorrer toda la columna.
TAM_MUESTRA = 1_000


# ---------------------------------------------------------------------------
# Paso 2: vacíos a NULL
# ---------------------------------------------------------------------------
def limpiar_vacios(df: pd.DataFrame) -> None:
    """Quita espacios en los extremos y convierte vacíos y marcadores en NULL."""
    for columna in df.columns:
        valores = df[columna].str.strip()
        es_nulo = valores.eq("")

        marcadores = MARCADORES_NULOS.get(columna)
        if marcadores:
            es_nulo |= valores.str.lower().isin(marcadores)

        df[columna] = valores.mask(es_nulo)

# ---------------------------------------------------------------------------
# Ofuscación de coordenadas geográficas
# ---------------------------------------------------------------------------
COLUMNAS_COORDENADAS = ("latitude", "longitude")
DECIMALES_COORDENADAS = 2


def ofuscar_coordenadas(df: pd.DataFrame) -> None:
    """
    Trunca latitud y longitud a 2 decimales para reducir
    la precisión geográfica en la capa Silver.

    Los valores nulos se conservan.
    Los valores originales permanecen intactos en Bronze.
    """
    for columna in COLUMNAS_COORDENADAS:
        if columna not in df.columns:
            continue

        valores = pd.to_numeric(df[columna], errors="raise")
        factor = 10 ** DECIMALES_COORDENADAS

        df[columna] = valores.map(
            lambda valor: (
                f"{int(valor * factor) / factor:.{DECIMALES_COORDENADAS}f}"
                if pd.notna(valor)
                else None
            )
        )
# ---------------------------------------------------------------------------
# Inferencia de tipos
# ---------------------------------------------------------------------------
def _todos_cumplen(valores: pd.Series, condicion) -> bool:
    """Evalúa la condición primero en una muestra y luego en toda la columna."""
    if not condicion(valores.head(TAM_MUESTRA)).all():
        return False
    return bool(condicion(valores).all())


def _es_json(valores: pd.Series) -> bool:
    """Indica si todos los valores son JSON válidos."""
    try:
        for valor in valores:
            json.loads(valor)
    except ValueError:
        return False
    return True


def _cabe_en_bigint(enteros: pd.Series) -> bool:
    """Comprueba que todos los enteros caben en BIGINT (64 bits con signo)."""
    largos = enteros.str.lstrip("-").str.len()
    grandes = enteros[largos >= 19]  # con menos de 19 dígitos siempre cabe
    return all(abs(int(valor)) <= MAX_BIGINT for valor in grandes)


def limpiar_numero(valores: pd.Series) -> pd.Series:
    """Quita símbolos de moneda, separadores de miles, '%' y espacios."""
    return valores.str.replace(CARACTERES_NO_NUMERICOS, "", regex=True)


def inferir_tipo(serie: pd.Series) -> str:
    """Devuelve el tipo de PostgreSQL que corresponde a una columna limpia."""
    valores = serie.dropna()
    if valores.empty:
        return "TEXT"

    if _todos_cumplen(valores, lambda s: s.isin(list(VALORES_BOOLEANOS))):
        return "BOOLEAN"

    if _todos_cumplen(valores, lambda s: s.str.fullmatch(PATRON_FECHA)):
        return "DATE"

    if _todos_cumplen(
        valores, lambda s: limpiar_numero(s).str.fullmatch(PATRON_DECIMAL)
    ):
        numeros = limpiar_numero(valores)
        if numeros.str.fullmatch(PATRON_ENTERO).all() and _cabe_en_bigint(numeros):
            return "BIGINT"
        return "NUMERIC"

    if _todos_cumplen(valores, lambda s: s.str.match(r"[\[{]")) and _es_json(valores):
        return "JSONB"

    return "TEXT"


# ---------------------------------------------------------------------------
# Pasos 3, 4 y 5: conversión
# ---------------------------------------------------------------------------
def convertir(serie: pd.Series, tipo: str) -> pd.Series:
    """Convierte una columna de texto al tipo de pandas equivalente."""
    if tipo == "BOOLEAN":
        return serie.map(VALORES_BOOLEANOS).astype("boolean")

    if tipo == "DATE":
        # errors="raise": una fecha imposible (p. ej. 2026-02-30) detiene el ETL.
        return pd.to_datetime(serie, format="%Y-%m-%d", errors="raise")

    if tipo == "BIGINT":
        # astype desde texto es exacto; pd.to_numeric pasaría por float y
        # perdería precisión en identificadores de 19 dígitos.
        return limpiar_numero(serie).astype("Int64")

    if tipo == "NUMERIC":
        return limpiar_numero(serie).astype("Float64")

    # TEXT y JSONB se mantienen como texto; PostgreSQL valida el JSON al cargar.
    return serie


def transformar(df: pd.DataFrame) -> dict[str, str]:
    """Limpia y tipa el DataFrame en el mismo objeto.

    Devuelve un diccionario {columna: tipo PostgreSQL} con el esquema que
    se usará para crear la tabla en Silver.
    """
    limpiar_vacios(df)

    ofuscar_coordenadas(df)

    tipos = {}
    for columna in df.columns:
        if columna in COLUMNAS_PROCEDENCIA:
            tipos[columna] = "TEXT"
            continue

        tipo = inferir_tipo(df[columna])
        df[columna] = convertir(df[columna], tipo)
        tipos[columna] = tipo

    resumen = pd.Series(tipos).value_counts().to_dict()
    log.info("  Tipos asignados: %s", resumen)
    return tipos


def validar_clave(df: pd.DataFrame, clave: tuple[str, ...]) -> None:
    """Verifica que la clave primaria no tenga nulos ni duplicados."""
    faltantes = [columna for columna in clave if columna not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas de la clave primaria: {faltantes}")

    nulos = int(df[list(clave)].isna().any(axis=1).sum())
    if nulos:
        raise ValueError(f"{nulos} filas tienen nulos en la clave {clave}")

    duplicados = int(df.duplicated(subset=list(clave)).sum())
    if duplicados:
        raise ValueError(f"{duplicados} filas duplican la clave {clave}")

