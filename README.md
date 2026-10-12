# Airbnb Data Lake --- Ciudad de México

## Descripción del proyecto
Data Lake local para organizar y preparar
datos de Inside Airbnb correspondientes a distintos snapshots de Ciudad
de México. Hasta ahora se han desarrollado dos capas:

-   **Bronze:** conserva los archivos de origen y sus versiones
    unificadas de un año completo (MARCH, JUNE, SEP) en CSV y GeoJSON.
-   **Silver:** almacena los datos estructurados y preparados en una
    base de datos SQLite.

El flujo ETL transforma y carga datos desde Bronze hacia Silver. 

## 2. Arquitectura y estructura del proyecto


``` text
airbnb-data-lake/
├── requirements.txt
├── README.md
├── data-lake/
│   ├── bronze/
│   │   ├── listings/
│   │   │   ├── listings-MARCH.csv
│   │   │   ├── listings-JUNE.csv
│   │   │   ├── listings-SEP.csv
│   │   │   └── unido/listings_unido.csv
│   │   ├── reviews/
│   │   │   ├── reviews-MARCH.csv
│   │   │   ├── reviews-JUNE.csv
│   │   │   ├── reviews-SEP.csv
│   │   │   └── unido/reviews_unido.csv
│   │   ├── neighbourhoods/
│   │   │   ├── neighbourhoods-MARCH.csv
│   │   │   ├── neighbourhoods-JUNE.csv
│   │   │   ├── neighbourhoods-SEP.csv
│   │   │   └── unido/neighbourhoods_unido.csv
│   │   └── geojson/
│   │       ├── neighbourhoods-MARCH.geojson
│   │       ├── neighbourhoods-JUNE.geojson
│   │       ├── neighbourhoods-SEP.geojson
│   │       └── unido/neighbourhoods_unido.geojson
│   ├── silver/
│   │   └── airbnb_silver.db
│   ├── scripts/
│   └── reportes/
└── sql/
    └── create_silver.sql
```

Los archivos etiquetados `MARCH`, `JUNE` y `SEP` identifican snapshots o
capturas de los datos (un tercio del año), no los meses específicos que llevan por nombre.

### Capa Bronze

Bronze organiza los CSV y GeoJSON por conjunto de datos. Los archivos
dentro de `unido/` unifican los snapshots e
incorporan `_source_file` para conservar la procedencia de cada
registro.

### Capa Silver

Silver se implementa en SQLite, en `data-lake/silver/airbnb_silver.db`.
La base contiene las siguientes tablas:

-   `source_snapshots`: registro de los snapshots de origen
-   `listings_snapshot`: registros de alojamientos por snapshot
-   `reviews_snapshot`: registros de reseñas por snapshot
-   `neighbourhoods`: catálogo de barrios.
-   `neighbourhood_geometries`: geometrías de los barrios
-   `etl_runs`: registro de ejecuciones del ETL y sus resultados


Existe un catálogo de datos que documenta los formatos y significados de
los campos en caso de duda.


## 3. Preparación del entorno

Ejecutar los siguientes comandos desde la raíz del repositorio.

Crear y activar un entorno virtual:

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Instalar las dependencias:

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verificar que Python y SQLite estén disponibles:

``` bash
python --version
sqlite3 --version
```

## 4. Ejecución en orden del ETL

### Paso 1. Crear la base de datos Silver

``` bash
python data-lake/scripts/crearBD.py
```

Este script crea la base de datos SQLite y aplica el esquema definido en
`sql/create_silver.sql`.

### Paso 2. Preparar las tablas de alojamientos y reseñas

``` bash
python data-lake/scripts/preparar_tablas.py
```

El script utiliza los encabezados de los CSV unificados para preparar
`listings_snapshot` y `reviews_snapshot`. Las columnas de origen se
definen como `TEXT`; además, se incorporan `snapshot_id` y `source_file`
para identificar el snapshot y la procedencia del registro.

### Paso 3. Cargar barrios y geometrías

``` bash
python data-lake/scripts/cargar_neighbourhoods.py
```

Este paso lee el CSV y el GeoJSON unificados de barrios, valida su
consistencia y carga los 16 barrios y sus geometrías. También
registra los snapshots de origen en `source_snapshots`.

### Paso 4. Cargar listings y reviews

``` bash
python data-lake/scripts/cargar_datos.py all
```

El argumento `all` ejecuta la carga de los conjuntos de alojamientos y
reseñas. El proceso identifica el snapshot a partir del archivo de
origen, carga los registros por lotes y registra las ejecuciones en
`etl_runs`.

La carga utiliza las claves compuestas `(snapshot_id, id)` y una
operación de actualización ante conflictos, de modo que volver a
ejecutar el proceso no duplica las claves existentes. El script registra
el estado de la ejecución (`RUNNING`, `SUCCESS` o `FAILED`), las marcas
de tiempo, los conteos procesados y el mensaje de error cuando
corresponde.

> **Importante:** `preparar_tablas.py` utiliza
> `CREATE TABLE IF NOT EXISTS`. **Si cambian los encabezados de los CSV,
> la tabla existente no se migra automáticamente.** Antes de cambiar el
> esquema, se debe revisar y adaptar el procedimiento de preparación de
> tablas.

## 6. Scripts auxiliares

Además de los scripts de carga, el directorio `data-lake/scripts/`
contiene scripts que utilicé mientras trabajaba para preparar y validar lo que iba haciendo:

  -----------------------------------------------------------------------
  Script                              Propósito
  ----------------------------------- -----------------------------------
  `unir_csv.py`                       Unir archivos CSV de un mismo
                                      conjunto de datos.

  `unir_geojson.py`                   Unir archivos GeoJSON de
                                      barrios.

  `verificar_unificacion.py`          Verificar resultados de la
                                      unificación.

  `verificar_ids.py`                  Revisar identificadores de los
                                      datos.

  `verificar_claves_etl.py`           Comprobar claves relacionadas con
                                      la carga ETL.

  `auditar_nulos_listings.py`         Auditar valores nulos en listings.

  `auditar_nulos_silver.py`           Auditar valores nulos en Silver.

  `perfilar_listings.py`              Perfilar campos de listings.

  `validar_precios.py`                Validar la representación y
                                      conversión de los campos de precio.
  -----------------------------------------------------------------------

Los scripts de auditoría y validación generan resultados que sirven como control de calidad y evidencia.

## 7. Transformaciones y reglas de calidad

El proceso de carga aplica las siguientes reglas:

-   **Identificación del snapshot:** se deriva de la etiqueta presente
    en el nombre del archivo de origen (`MARCH`, `JUNE` o `SEP`).
-   **Procedencia:** el valor de `_source_file` se conserva en la
    columna `source_file` de Silver.
-   **Valores vacíos:** las cadenas vacías se convierten en `NULL`.
-   **Marcadores de ausencia:** en `host_verifications`, el valor
    literal `None` se transforma en `NULL`. En `name` y `description`,
    el texto literal `none`, sin distinguir mayúsculas y minúsculas, se
    transforma en `NULL`.
-   **Claves:** se valida que existan identificadores y que no haya
    duplicados de la clave compuesta dentro de los CSV unificados.
-   **Barrios y geometrías:** se verifica la correspondencia de nombres
    entre CSV y GeoJSON y la consistencia de las geometrías duplicadas.
    Silver mantiene una geometría canónica por barrio.
-   **Precios:** se conservaron las columnas de origen; las validaciones
    efectuadas no detectaron valores no convertibles en los campos de
    precio examinados.

Los campos de listings y reviews se almacenan como texto en SQLite. Las
validaciones de formato no equivalen a convertir esos campos a tipos
numéricos o de fecha dentro de la base de datos.

## 8. Validación del resultado

Después de ejecutar el ETL, se verificaron los siguientes resultados:

  Conjunto o control                                         Resultado
  ---------------------------------------------- ---------------------
  Listings en Silver                                            85.630
  Reviews en Silver                                          4.986.773
  Barrios canónicos                                                 16
  Geometrías canónicas                                              16
  Snapshots registrados                                              3
  Claves compuestas duplicadas en listings                           0
  Claves compuestas duplicadas en reviews                            0
  Identificadores vacíos en listings y reviews                       0
  `PRAGMA integrity_check`                                        `ok`
  `PRAGMA foreign_key_check`                       Sin filas devueltas

Los conteos de listings y reviews de Silver coinciden con los de Bronze
para cada snapshot. También se reejecutó la carga y se comprobó que los
conteos y las claves se mantuvieran.


## 9. Limitaciones encontradas

En la comparación de referencias entre reseñas y alojamientos se
identificaron 20.430 reseñas del snapshot `SEP` cuyo `listing_id` no
aparece en listings del mismo snapshot. De los identificadores
involucrados, 85 aparecen en listings de `MARCH` y 1.494 no se
encontraron en los listings unificados disponibles.

No es una pérdida durante el ETL, si no que una limitación de los csv originales. 

