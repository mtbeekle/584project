import argparse
from pathlib import Path
import subprocess

import pandas as pd

from checks.missingdata import check_missing_data
from checks.capacitors import check_capacitors
from checks.fuses import check_open_fuses
from checks.conductorheight import check_conductor_height
from checks.customercount import check_customer_count
from checks.loads import check_connected_kva
from checks.incorrectphases import check_incorrect_phases
from checks.mismatched_conductors import check_conductor_mismatch
from mdb_utils import connect_to_mdb, find_default_mdb_file, list_user_tables, read_table
from reports import write_validation_report
from topology import check_loops, check_unfed_sections


PROJECT_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = PROJECT_DIR / "data" / "exports"
DEFAULT_OUTPUT_FILE = EXPORTS_DIR / "synergi_validation_results.xlsx"
TRANSFORMER_TABLE_NAMES = (
    "InstDTrans",
    "InstPrimaryTransformers",
    "InstSubstationTransformers",
)


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


def load_optional_transformer_tables(connection, available_tables: list[str]) -> pd.DataFrame:
    transformer_frames = []
    available_table_set = set(available_tables)

    for table_name in TRANSFORMER_TABLE_NAMES:
        if table_name not in available_table_set:
            continue

        transformer_table = read_table(connection, table_name)
        transformer_table["TransformerSourceTable"] = table_name
        transformer_frames.append(transformer_table)

    if not transformer_frames:
        return pd.DataFrame()

    return pd.concat(transformer_frames, ignore_index=True, sort=False)


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

        user_tables = list_user_tables(conn)
        for table_name in user_tables:
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
        transformers = load_optional_transformer_tables(conn, user_tables)

        print(f"Nodes Loaded: {len(nodes)}")
        print(f"Sections Loaded: {len(sections)}")
        print(f"Loads Loaded: {len(loads)}")
        print(f"Capacitors Loaded: {len(capacitors)}")
        print(f"Fuses Loaded: {len(fuses)}")
        print(f"Transformers Loaded: {len(transformers)}")

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
            sections,
            transformers=transformers,
            nodes=nodes,
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

        customer_count_results = check_customer_count(
            loads
        )

        conductor_mismatch_results = check_conductor_mismatch(
            sections
        )

        incorrect_phase_results = check_incorrect_phases(
            sections
        )

        loop_results = check_loops(sections)
        unfed_topology_results = check_unfed_sections(sections)
        topology_results = {
            **loop_results,
            **unfed_topology_results,
        }

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
            "Conductor height issues:",
            len(height_results['conductor_height_issues'])
        )

        print(
            "Potential loop/meshed topology review sections:",
            len(loop_results["loop_sections"])
        )

        print(
            "Isolated topology component review sections:",
            len(unfed_topology_results["unfed_sections"])
        )

        print(
            "Sections with load records but no connected load:",
            len(load_results['no_connected_kva'])
        )

        print(
            "Customer count issues:",
            len(customer_count_results['customer_count_issues'])
        )

        print(
            "Conductor configuration issues:",
            len(conductor_mismatch_results['conductor_issues'])
        )

        print(
            "Incorrect phase issues:",
            len(incorrect_phase_results['incorrect_phases'])
        )

        write_validation_report(
            output_file,
            mdb_file,
            missing_results,
            capacitor_results,
            fuse_results,
            height_results,
            load_results,
            customer_count_results,
            conductor_mismatch_results,
            incorrect_phase_results,
            topology_results,
            tool_version=get_tool_version(),
        )

        print(f"\nValidation report exported to:\n{output_file}")

    print("\nMDB connection closed.")


if __name__ == "__main__":
    main()
