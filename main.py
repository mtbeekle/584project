import argparse
from pathlib import Path
import subprocess

from missingdata import check_missing_data
from capacitors import check_capacitors
from fuses import check_open_fuses
from conductorheight import check_conductor_height
from loads import check_connected_kva
from mdb_utils import connect_to_mdb, find_default_mdb_file, list_user_tables, read_table
from reports import write_validation_report
from topology import check_loops


PROJECT_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = PROJECT_DIR / "data" / "exports"
DEFAULT_OUTPUT_FILE = EXPORTS_DIR / "synergi_validation_results.xlsx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Synergi Electric model validation checks."
    )
    parser.add_argument(
        "--mdb-file",
        type=Path,
        default=None,
        help=(
            "Path to the Synergi .mdb/.accdb file. "
            "Default: the only .mdb/.accdb file in data/raw."
        ),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Path for the Excel validation report. Default: data/exports/synergi_validation_results.xlsx",
    )
    return parser.parse_args()


def load_table(connection, table_name: str):
    try:
        return read_table(connection, table_name)
    except Exception as exc:
        raise RuntimeError(f"Could not load required table [{table_name}]") from exc


def get_tool_version() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    version = result.stdout.strip()
    return version or None


def main() -> None:
    args = parse_args()
    mdb_file = args.mdb_file if args.mdb_file else find_default_mdb_file()
    output_file = args.output_file

    if not mdb_file.is_absolute():
        mdb_file = PROJECT_DIR / mdb_file

    if not output_file.is_absolute():
        output_file = PROJECT_DIR / output_file

    if not mdb_file.exists():
        raise FileNotFoundError(mdb_file)

    print(f"MDB file found: {mdb_file}")

    with connect_to_mdb(mdb_file) as conn:
        print("Connected successfully!")

        # =====================================================
        # LIST TABLES
        # =====================================================

        print("\n========================")
        print("TABLES IN MDB")
        print("========================\n")

        for table_name in list_user_tables(conn):
            print(table_name)

        # =====================================================
        # LOAD TABLES
        # =====================================================

        print("\n========================")
        print("LOADING TABLES")
        print("========================")

        nodes = load_table(conn, "Node")
        sections = load_table(conn, "InstSection")
        loads = load_table(conn, "Loads")
        capacitors = load_table(conn, "InstCapacitors")
        fuses = load_table(conn, "InstFuses")

        print(f"Nodes Loaded: {len(nodes)}")
        print(f"Sections Loaded: {len(sections)}")
        print(f"Loads Loaded: {len(loads)}")
        print(f"Capacitors Loaded: {len(capacitors)}")
        print(f"Fuses Loaded: {len(fuses)}")

        # =====================================================
        # DISPLAY COLUMNS
        # =====================================================

        print("\n========================")
        print("NODE COLUMNS")
        print("========================")
        print(nodes.columns.tolist())

        print("\n========================")
        print("SECTION COLUMNS")
        print("========================")
        print(sections.columns.tolist())

        # =====================================================
        # RUN VALIDATION CHECKS
        # =====================================================

        missing_results = check_missing_data(sections)

        capacitor_results = check_capacitors(
            capacitors,
            sections
        )

        fuse_results = check_open_fuses(
            fuses,
            sections
        )

        height_results = check_conductor_height(
            sections
        )

        load_results = check_connected_kva(
            loads,
            sections
        )

        topology_results = check_loops(sections)

        # =====================================================
        # PRINT RESULTS
        # =====================================================

        print("\n========================")
        print("VALIDATION RESULTS")
        print("========================\n")

        print(
            "Sections missing connectivity:",
            len(missing_results['missing_connectivity'])
        )

        print(
            "Sections missing length:",
            len(missing_results['missing_length'])
        )

        print(
            "Sections missing phase data:",
            len(missing_results['missing_phase'])
        )

        print(
            "Sections missing conductor:",
            len(missing_results['missing_conductor'])
        )

        print(
            "Duplicate Section IDs:",
            len(missing_results['duplicate_sections'])
        )

        print(
            "Capacitor issues:",
            len(capacitor_results['capacitor_issues'])
        )

        print(
            "Open fuses:",
            len(fuse_results['open_fuses'])
        )

        print(
            "Unfed sections:",
            len(fuse_results['unfed_sections'])
        )

        print(
            "Conductor height issues:",
            len(height_results['conductor_height_issues'])
        )

        print(
            "Potential loop sections:",
            len(topology_results['loop_sections'])
        )

        print(
            "Sections with load records but no connected load:",
            len(load_results['no_connected_kva'])
        )

        write_validation_report(
            output_file,
            mdb_file,
            missing_results,
            capacitor_results,
            fuse_results,
            height_results,
            load_results,
            topology_results,
            tool_version=get_tool_version(),
        )

        print(f"\nValidation report exported to:\n{output_file}")

    print("\nMDB connection closed.")


if __name__ == "__main__":
    main()
