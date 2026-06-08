from pathlib import Path

import pandas as pd
import pyodbc


ACCESS_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"
PROJECT_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = PROJECT_DIR / "data" / "raw"


def find_default_mdb_file(raw_data_dir: Path = RAW_DATA_DIR) -> Path:
    mdb_files = sorted(raw_data_dir.glob("*.mdb")) + sorted(raw_data_dir.glob("*.accdb"))

    if not mdb_files:
        raise FileNotFoundError(
            "No .mdb or .accdb file found in "
            f"{raw_data_dir}. Put the Synergi export there or pass --mdb-path."
        )

    if len(mdb_files) > 1:
        files = "\n".join(f"  - {path.name}" for path in mdb_files)
        raise ValueError(
            "More than one Access database was found in "
            f"{raw_data_dir}. Pass --mdb-path to choose one:\n{files}"
        )

    return mdb_files[0]


def connect_to_mdb(mdb_path: Path) -> pyodbc.Connection:
    if not mdb_path.exists():
        raise FileNotFoundError(f"MDB file not found: {mdb_path}")

    connection_string = (
        f"DRIVER={{{ACCESS_DRIVER}}};"
        f"DBQ={mdb_path.resolve()};"
    )
    return pyodbc.connect(connection_string)


def list_user_tables(connection: pyodbc.Connection) -> list[str]:
    cursor = connection.cursor()
    tables = []

    for row in cursor.tables(tableType="TABLE"):
        table_name = row.table_name
        if not table_name.startswith("MSys"):
            tables.append(table_name)

    return sorted(tables)


def quote_access_name(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def read_table(connection: pyodbc.Connection, table_name: str) -> pd.DataFrame:
    quoted_table = quote_access_name(table_name)
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM {quoted_table}")
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame.from_records(rows, columns=columns)
