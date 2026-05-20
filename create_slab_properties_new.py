import sqlite3

import pandas as pd


def create_database_slab_from_excel(database_name: str, excel_path: str, sheet_name: str | int = 0):
    """
    Reads slab properties from an Excel file and writes them into an SQLite database table 'slab_properties'.

    Header row in the Excel is row 14 -> pandas header index 13.
    Only these columns are imported (others in Excel are ignored):
    NAME, RAENDER, LX, LY, MX_POS, MX_NEG, MY_POS, MY_NEG, V_POS, V_NEG, W, F
    """
    # Header is on Excel row 14 => header=13 (0-based)
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=13)

    # Normalize column names (strip spaces)
    df.columns = [str(c).strip() for c in df.columns]

    needed = ["NAME", "RAENDER", "LX", "LY", "MX_POS", "MX_NEG", "MY_POS", "MY_NEG", "V_POS", "V_NEG", "W", "F"]
    missing = [column for column in needed if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required slab-property columns in Excel sheet: {missing}")
    df = df[needed].dropna(how="all")

    # Convert comma decimals to dot decimals + numeric conversion
    numeric_cols = ["LX", "LY", "MX_POS", "MX_NEG", "MY_POS", "MY_NEG", "V_POS", "V_NEG", "W", "F"]
    for c in numeric_cols:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace("\u00a0", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Create / replace table
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS slab_properties;")
    cursor.execute(
        """
        CREATE TABLE slab_properties (
            NAME TEXT,
            RAENDER TEXT,
            LX REAL,
            LY REAL,
            MX_POS REAL,
            MX_NEG REAL,
            MY_POS REAL,
            MY_NEG REAL,
            V_POS REAL,
            V_NEG REAL,
            W REAL,
            F REAL
        );
        """
    )

    insert_sql = """
        INSERT INTO slab_properties
        (NAME, RAENDER, LX, LY, MX_POS, MX_NEG, MY_POS, MY_NEG, V_POS, V_NEG, W, F)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    cursor.executemany(insert_sql, list(df.itertuples(index=False, name=None)))

    connection.commit()
    connection.close()


def show_database_contents(database_name):
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT NAME, RAENDER, LX, LY, MX_POS, MX_NEG, MY_POS, MY_NEG, V_POS, V_NEG, W, F
        FROM slab_properties
        ORDER BY NAME, RAENDER;
        """
    )
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]

    # Print the whole table (all rows)
    print("\t".join(column_names))
    for r in rows:
        print("\t".join("" if v is None else str(v) for v in r))

    connection.close()


if __name__ == "__main__":
    database_name = "slab_properties.db"
    excel_path = "/Users/jonathanbieg/Documents/Master Thesis/1_Code/Python Repository/SDSD_Bieg/Database/260507_CEDRUS-Platten-Resultate.xlsx"
    sheet_name = 0

    create_database_slab_from_excel(database_name, excel_path, sheet_name=sheet_name)
    show_database_contents(database_name)
    # show what datatypes are in the database
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()
    cursor.execute("PRAGMA table_info(slab_properties);")
    print("\nDatabase table schema:")
    for row in cursor.fetchall():
        print(row)
    connection.close()

