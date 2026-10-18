# Airbnb Data Lake --- Ciudad de México

## 1. Descripción del proyecto
Data Lake local para organizar y preparar
datos de Inside Airbnb correspondientes a distintos snapshots de Ciudad
de México. Hasta ahora se han desarrollado dos capas:

-   **Bronze:** conserva los archivos de origen de un año completo
    (MARCH, JUNE, SEP) en CSV y GeoJSON, sin modificarlos.
-   **Silver:** almacena los datos limpios y tipados en una base de
    datos PostgreSQL que se levanta con Docker.

El flujo ETL lee los snapshots de Bronze, los unifica en memoria con
pandas, los limpia, infiere el tipo de cada columna y los carga en
Silver. Todo se ejecuta con un único comando (`main.py`).

## 2. Arquitectura y estructura del proyecto


``` text
airbnb-data-lake/
├── requirements.txt
├── README.md
├── docker-compose.yml
├── .env.example
├── data-lake/
│   ├── bronze/
│   │   ├── listings/
│   │   │   ├── listings-MARCH.csv
│   │   │   ├── listings-JUNE.csv
│   │   │   └── listings-SEP.csv
│   │   ├── reviews/
│   │   │   ├── reviews-MARCH.csv
│   │   │   ├── reviews-JUNE.csv
│   │   │   └── reviews-SEP.csv
│   │   ├── neighbourhoods/
│   │   │   ├── neighbourhoods-MARCH.csv
│   │   │   ├── neighbourhoods-JUNE.csv
│   │   │   └── neighbourhoods-SEP.csv
│   │   └── geojson/
│   │       ├── neighbourhoods-MARCH.geojson
│   │       ├── neighbourhoods-JUNE.geojson
│   │       └── neighbourhoods-SEP.geojson
│   ├── scripts/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── extraccion.py
│   │   ├── transformacion.py
│   │   ├── carga.py
│   │   ├── reportes.py
│   │   └── esquema.py
│   └── reportes/
└── sql/
    └── create_silver_postgres.sql
```

Los archivos etiquetados `MARCH`, `JUNE` y `SEP` identifican snapshots o
capturas de los datos (un tercio del año), no los meses específicos que llevan por nombre.

Los CSV de Bronze están en `.gitignore` por su tamaño, por lo que solo
existen localmente y deben copiarse a sus carpetas antes de ejecutar el
ETL. Los GeoJSON sí se versionan.

### Capa Bronze

Bronze organiza los CSV y GeoJSON por conjunto de datos, un archivo por
snapshot, con el patrón `<prefijo>-<ETIQUETA>.<extensión>` (por ejemplo,
`listings-SEP.csv`). La etiqueta del nombre se usa como `snapshot_id`.
El ETL no modifica estos archivos ni escribe archivos intermedios: la
unificación de los snapshots se hace en memoria.

Para agregar un snapshot nuevo basta con dejar el archivo en su carpeta
siguiendo el mismo patrón (por ejemplo, `listings-DEC.csv`) y volver a
ejecutar el ETL.

### Capa Silver

Silver se implementa en PostgreSQL 17 (contenedor `airbnb_silver_postgres`,
puerto `5433`). La base contiene las siguientes tablas:

-   `silver_listings`: alojamientos por snapshot. Clave `(snapshot_id, id)`.
-   `silver_reviews`: reseñas por snapshot. Clave `(snapshot_id, id)`.
-   `silver_neighbourhoods`: catálogo de barrios por snapshot. Clave
    `(snapshot_id, neighbourhood)`.
-   `silver_neighbourhood_geometries`: geometrías de los barrios por
    snapshot, con la geometría en `JSONB`. Clave
    `(snapshot_id, neighbourhood)`.
-   `silver_etl_runs`: registro de ejecuciones del ETL y sus resultados.

Todas las tablas de datos incluyen las columnas `snapshot_id` y
`source_file` para conservar la procedencia de cada registro.

El esquema real (tablas, tipos inferidos, claves y comentarios) se
exporta automáticamente con `pg_dump` al final de cada ejecución en
`sql/create_silver_postgres.sql`. Ese archivo es solo documentación: el
ETL no lo lee y no debe editarse a mano.

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

Crear el archivo de credenciales a partir del ejemplo (lo usan tanto
`docker-compose.yml` como `config.py`):

``` bash
cp .env.example .env
```

Levantar PostgreSQL:

``` bash
docker compose up -d
```

Verificar que Python y el contenedor estén disponibles:

``` bash
python --version
docker compose ps
```

Para detener la base de datos se usa `docker compose down` (los datos
se conservan en el volumen) o `docker compose down -v` (borra también
los datos).

## 4. Ejecución del ETL

El ETL completo se ejecuta con un solo comando, con PostgreSQL levantado:

``` bash
python data-lake/scripts/main.py
```

También se pueden procesar solo algunos conjuntos de datos
(`listings`, `reviews`, `neighbourhoods`, `geojson`) u omitir los
reportes de calidad:

``` bash
python data-lake/scripts/main.py listings reviews
python data-lake/scripts/main.py --sin-reportes
```

Para cada conjunto de datos, `main.py` ejecuta los siguientes pasos:

### Paso 1. Unificar los snapshots de Bronze

`extraccion.py` lee todos los archivos del conjunto (uno por snapshot) y
los une en un único DataFrame. Todas las columnas se leen como texto y a
cada fila se le agregan `snapshot_id` y `source_file`. Los GeoJSON se
convierten en una fila por barrio, con sus propiedades como columnas y
la geometría como texto JSON. Si un snapshot trae columnas distintas al
primero, se muestra una advertencia.

### Paso 2. Auditar vacíos en Bronze

`reportes.py` cuenta las celdas vacías por columna y snapshot antes de
limpiar los datos.

### Paso 3. Limpiar y tipar los datos

`transformacion.py` convierte los vacíos en `NULL`, infiere el tipo de
cada columna a partir de sus valores y la convierte (ver sección 6).
Luego valida que la clave primaria no tenga nulos ni duplicados.

### Paso 4. Cargar en PostgreSQL

`carga.py` recarga cada tabla completa dentro de una sola transacción:
`DROP TABLE` → `CREATE TABLE` (con los tipos inferidos y la clave
primaria) → `COPY`. Si algo falla, PostgreSQL revierte todo y la tabla
anterior queda intacta.

Cada ejecución queda registrada en `silver_etl_runs` con su estado
(`RUNNING`, `SUCCESS` o `FAILED`), las marcas de tiempo, las filas de
origen y cargadas, y el mensaje de error cuando corresponde.

### Paso 5. Validar la carga

Se cuentan los `NULL` por columna en Silver y se comparan las filas por
snapshot entre Bronze y Silver. Los conteos de Silver se calculan con SQL
dentro de PostgreSQL para no volver a traer millones de filas a memoria.

Al terminar todos los conjuntos, `esquema.py` exporta el esquema con
`pg_dump` (usa el `pg_dump` local o, si falla, el del contenedor) y se
muestra un resumen. El proceso termina con error si algún conteo de
Bronze no coincide con Silver.

> **Importante:** como cada tabla se borra y se vuelve a crear en cada
> ejecución, el ETL es repetible: volver a ejecutarlo (por ejemplo, tras
> agregar un snapshot nuevo) deja Silver igual a Bronze sin duplicar
> registros. Por lo mismo, **cualquier cambio hecho a mano en las tablas
> de Silver se pierde al reejecutar el ETL.**

## 5. Módulos del ETL

El directorio `data-lake/scripts/` contiene los siguientes módulos:

  -----------------------------------------------------------------------
  Script                              Propósito
  ----------------------------------- -----------------------------------
  `main.py`                           Punto de entrada único; ejecuta
                                      el ETL completo.

  `config.py`                         Configuración central: rutas,
                                      conjuntos de datos (`DATASETS`),
                                      reglas de limpieza y conexión.

  `extraccion.py`                     Lectura y unificación de los
                                      snapshots de Bronze.

  `transformacion.py`                 Limpieza de vacíos, inferencia y
                                      conversión de tipos, validación
                                      de claves.

  `carga.py`                          Creación de tablas, carga con
                                      `COPY` y bitácora `silver_etl_runs`.

  `reportes.py`                       Reportes de nulos, tipos y
                                      validación de conteos.

  `esquema.py`                        Exportación del esquema de Silver
                                      con `pg_dump`.
  -----------------------------------------------------------------------

Para agregar un nuevo conjunto de datos basta con registrarlo en
`DATASETS` dentro de `config.py`; el resto de los módulos es genérico.

### Reportes de calidad

Los reportes se escriben en `data-lake/reportes/` y sirven como
control de calidad y evidencia:

  -----------------------------------------------------------------------
  Archivo                             Contenido
  ----------------------------------- -----------------------------------
  `bronze/<dataset>/`                 `nulos_por_snapshot.csv` y
                                      `nulos_resumen.csv`: vacíos por
                                      columna antes de limpiar.

  `silver/<tabla>/`                   `nulos_por_snapshot.csv` y
                                      `nulos_resumen.csv`: `NULL` por
                                      columna después de cargar.

  `silver/<tabla>/tipos.csv`          Tipo de PostgreSQL asignado a cada
                                      columna.

  `validacion_carga.csv`              Filas por snapshot en Bronze
                                      frente a Silver, para todas las
                                      tablas.
  -----------------------------------------------------------------------

Al comparar los reportes de nulos de Bronze y Silver se ve el efecto de
la limpieza.

## 6. Transformaciones y reglas de calidad

El proceso de carga aplica las siguientes reglas:

-   **Identificación del snapshot:** se deriva de la etiqueta presente
    en el nombre del archivo de origen (`MARCH`, `JUNE` o `SEP`).
-   **Procedencia:** el nombre del archivo de origen se conserva en la
    columna `source_file` de Silver.
-   **Valores vacíos:** se quitan los espacios en los extremos y las
    celdas vacías o con solo espacios se convierten en `NULL`.
-   **Marcadores de ausencia:** en `host_verifications`, `name` y
    `description`, el texto literal `none`, sin distinguir mayúsculas y
    minúsculas, se transforma en `NULL`. Estos marcadores se configuran
    por columna en `MARCADORES_NULOS` y no se aplican a todas, porque
    por ejemplo en `host_name` y `reviewer_name` "Nan" o "Na" son
    nombres reales.
-   **Inferencia de tipos:** cada columna recibe un tipo según todos sus
    valores no nulos:
    -   `BOOLEAN`: solo contiene `t` / `f`.
    -   `DATE`: solo contiene fechas `AAAA-MM-DD`.
    -   `BIGINT`: enteros (tras quitar `$`, `,`, `%` y espacios) que
        caben en 64 bits.
    -   `NUMERIC`: números con decimales, con la misma limpieza.
    -   `JSONB`: listas u objetos JSON válidos (por ejemplo `amenities`
        o `geometry`).
    -   `TEXT`: todo lo demás, incluidas las columnas 100 % vacías.
-   **Precisión de identificadores:** los enteros se convierten
    directamente desde texto, sin pasar por números decimales, para no
    perder precisión en los IDs de 19 dígitos.
-   **Fechas inválidas:** una fecha imposible (por ejemplo `2026-02-30`)
    detiene el ETL.
-   **Claves:** se valida que existan las columnas de la clave primaria
    y que no haya nulos ni duplicados antes de cargar.

Como la inferencia es automática, nuevas columnas o snapshots no
requieren cambiar el código.

## 7. Validación del resultado

Después de cada ejecución, el ETL compara las filas por snapshot entre
Bronze y Silver y guarda el resultado en
`data-lake/reportes/validacion_carga.csv`. Los conteos esperados
para los conjuntos principales son:

  Conjunto o control                                         Resultado
  ---------------------------------------------- ---------------------
  Listings en Silver                                            85.630
  Reviews en Silver                                          4.986.773
  Snapshots por conjunto                                             3
  Claves duplicadas o nulas                                          0

Los conteos de Silver coinciden con los de Bronze para cada snapshot.
También se puede reejecutar el ETL y comprobar que los conteos y las
claves se mantengan.


## 8. Limitaciones encontradas

En la comparación de referencias entre reseñas y alojamientos se
identificaron 20.430 reseñas del snapshot `SEP` cuyo `listing_id` no
aparece en listings del mismo snapshot. De los identificadores
involucrados, 85 aparecen en listings de `MARCH` y 1.494 no se
encontraron en los listings disponibles.

No es una pérdida durante el ETL, si no que una limitación de los csv
originales. Por eso las tablas de Silver no declaran una clave foránea
entre reseñas y alojamientos.
