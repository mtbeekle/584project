import argparse
import csv
from pathlib import Path

import pandas as pd
import pyodbc


ACCESS_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"


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


def list_columns(connection: pyodbc.Connection, table_name: str) -> list[tuple[str, str]]:
    cursor = connection.cursor()
    columns = []

    for row in cursor.columns(table=table_name):
        columns.append((row.column_name, row.type_name))

    return columns


def quote_access_name(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def read_table(connection: pyodbc.Connection, table_name: str) -> pd.DataFrame:
    quoted_table = quote_access_name(table_name)
    return pd.read_sql(f"SELECT * FROM {quoted_table}", connection)


def export_table(connection: pyodbc.Connection, table_name: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataframe = read_table(connection, table_name)
    output_path = output_dir / f"{table_name}.csv"
    dataframe.to_csv(output_path, index=False, quoting=csv.QUOTE_MINIMAL)
    return output_path


def print_table_inventory(
    connection: pyodbc.Connection,
    tables: list[str],
    include_columns: bool,
    preview_rows: int,
) -> None:
    print(f"Found {len(tables)} user table(s).")

    for table_name in tables:
        print(f"\n{table_name}")

        if include_columns:
            columns = list_columns(connection, table_name)
            for column_name, type_name in columns:
                print(f"  - {column_name}: {type_name}")

        if preview_rows > 0:
            dataframe = read_table(connection, table_name)
            print(f"  Rows: {len(dataframe)}")
            if not dataframe.empty:
                print(dataframe.head(preview_rows).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect and export tables from a Synergi Electric .mdb file."
    )
    parser.add_argument("mdb_path", help="Path to the .mdb file to inspect.")
    parser.add_argument(
        "--columns",
        action="store_true",
        help="Show columns and Access data types for each table.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=0,
        help="Print the first N rows from each listed table.",
    )
    parser.add_argument(
        "--export-all",
        action="store_true",
        help="Export every user table to CSV.",
    )
    parser.add_argument(
        "--export",
        nargs="+",
        default=[],
        metavar="TABLE",
        help="Export selected table names to CSV.",
    )
    parser.add_argument(
        "--out",
        default="data/exports",
        help="Output directory for CSV exports. Default: data/exports",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mdb_path = Path(args.mdb_path)
    output_dir = Path(args.out)

    with connect_to_mdb(mdb_path) as connection:
        tables = list_user_tables(connection)
        print_table_inventory(connection, tables, args.columns, args.preview)

        requested_exports = tables if args.export_all else args.export
        if requested_exports:
            known_tables = set(tables)
            missing_tables = [table for table in requested_exports if table not in known_tables]
            if missing_tables:
                print("\nSkipped missing table(s):")
                for table_name in missing_tables:
                    print(f"  - {table_name}")

            print("\nExported CSV file(s):")
            for table_name in requested_exports:
                if table_name in known_tables:
                    output_path = export_table(connection, table_name, output_dir)
                    print(f"  - {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
