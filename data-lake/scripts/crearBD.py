
from pathlib import Path
import sqlite3

PROJECT_DIR = Path(__file__).resolve().parents[2]

# Rutas 
SQL_FILE = PROJECT_DIR / "sql" / "create_silver.sql"
DB_DIR = PROJECT_DIR / "data-lake" / "silver"
DB_FILE = DB_DIR / "airbnb_silver.db"

def main():
    if not SQL_FILE.is_file():
        raise FileNotFoundError(
            f"No se encontró el esquema SQL: {SQL_FILE}"
        )

    DB_DIR.mkdir(parents=True, exist_ok=True)
    sql_script = SQL_FILE.read_text(encoding="utf-8")

    with sqlite3.connect(DB_FILE) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(sql_script)

        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """).fetchall()

    print("Base de datos creada correctamente.")
    print(f"Ruta: {DB_FILE}")
    print("Tablas:")
    for (table_name,) in tables:
        print(f"  - {table_name}")

if __name__ == "__main__":
    main()
