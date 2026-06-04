"""Create the material/product SQLite database from the Excel source file."""

from pathlib import Path
import sqlite3

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_EXCEL_FILE = SCRIPT_DIR / "260126_Datenbankdefinition.xlsx"
DEFAULT_DATABASE_FILE = REPO_ROOT / "database_260126.db"


def create_database_from_excel(excel_file=DEFAULT_EXCEL_FILE, database_file=DEFAULT_DATABASE_FILE):
    excel_file = Path(excel_file)
    database_file = Path(database_file)

    df_products = pd.read_excel(excel_file, sheet_name="products", engine="openpyxl")
    df_material_prop = pd.read_excel(excel_file, sheet_name="material_prop", engine="openpyxl")
    df_floor_struc_prop = pd.read_excel(excel_file, sheet_name="floor_struc_prop", engine="openpyxl")
    df_connector_tcc = pd.read_excel(excel_file, sheet_name="connector_TCC", engine="openpyxl")

    database_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_file)
    try:
        df_products.to_sql("products", conn, if_exists="replace", index=False)
        df_material_prop.to_sql("material_prop", conn, if_exists="replace", index=False)
        df_floor_struc_prop.to_sql("floor_struc_prop", conn, if_exists="replace", index=False)
        df_connector_tcc.to_sql("connector_TCC", conn, if_exists="replace", index=False)
    finally:
        conn.close()

    return database_file


if __name__ == "__main__":
    path = create_database_from_excel()
    print(f"Datenbank erfolgreich erstellt: {path}")
