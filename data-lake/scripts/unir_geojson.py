
from pathlib import Path
import json


# Directorio data-lake/
BASE_DIR = Path(__file__).resolve().parent.parent

# Directorio de los GeoJSON originales
SOURCE_DIR = BASE_DIR / "bronze" / "geojson"

# Directorio y archivo de salida
OUTPUT_DIR = SOURCE_DIR / "unido"
OUTPUT_FILE = OUTPUT_DIR / "neighbourhoods_unido.geojson"

# Ajustar estos nombres a los archivos reales
FILES = [
    "neighbourhoods-MARCH.geojson",
    "neighbourhoods-JUNE.geojson",
    "neighbourhoods-SEP.geojson",
]


def unificar_geojson():
    features_combined = []
    reference_keys = None

    for filename in FILES:
        file_path = SOURCE_DIR / filename

        if not file_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el archivo: {file_path}"
            )

        print(f"\nLeyendo: {filename}")

        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if data.get("type") != "FeatureCollection":
            raise ValueError(
                f"{filename} no contiene una FeatureCollection."
            )

        features = data.get("features")

        if not isinstance(features, list):
            raise ValueError(
                f"El campo 'features' no es una lista en {filename}."
            )

        # Validar estructura básica de las entidades
        for feature in features:
            if not isinstance(feature, dict):
                raise ValueError(
                    f"Se encontró una entidad inválida en {filename}."
                )

            if feature.get("type") != "Feature":
                raise ValueError(
                    f"Una entidad no es de tipo Feature en {filename}."
                )

            if not isinstance(feature.get("properties"), dict):
                raise ValueError(
                    f"Una entidad no tiene propiedades válidas en {filename}."
                )

            if not isinstance(feature.get("geometry"), dict):
                raise ValueError(
                    f"Una entidad no tiene geometría válida en {filename}."
                )

        # Comprobar que las propiedades tengan las mismas claves
        for feature in features:
            keys = set(feature["properties"].keys())

            if reference_keys is None:
                reference_keys = keys
            elif keys != reference_keys:
                raise ValueError(
                    f"Las propiedades no coinciden en {filename}."
                )

        # Copiar cada entidad para no modificar el archivo original
        for feature in features:
            copied_feature = json.loads(json.dumps(feature))

            copied_feature["properties"]["_source_file"] = filename
            features_combined.append(copied_feature)

        print(f"Entidades leídas: {len(features):,}")

    # Construir una única FeatureCollection
    combined = {
        "type": "FeatureCollection",
        "features": features_combined,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            combined,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # Verificar que el archivo generado sea JSON válido
    with OUTPUT_FILE.open("r", encoding="utf-8") as file:
        verification = json.load(file)

    if len(verification["features"]) != len(features_combined):
        raise RuntimeError(
            "La verificación falló: las entidades no coinciden."
        )

    print("\nUnificación GeoJSON completada.")
    print(f"Archivos integrados: {len(FILES)}")
    print(f"Entidades totales: {len(verification['features']):,}")
    print(f"Archivo generado: {OUTPUT_FILE}")

    print("\nEntidades por archivo de origen:")
    counts = {}

    for feature in verification["features"]:
        source = feature["properties"]["_source_file"]
        counts[source] = counts.get(source, 0) + 1

    for source, count in counts.items():
        print(f"{source}: {count:,}")


if __name__ == "__main__":
    unificar_geojson()
