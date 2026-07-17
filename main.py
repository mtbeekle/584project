import argparse
from pathlib import Path
import subprocess

import pandas as pd

from checks.missingdata import check_missing_data
from checks.capacitors import check_capacitors
from checks.regulators import check_regulators
from checks.source_voltage import check_source_voltage
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


TRANSFORMER_TABLE_CANDIDATES = [
    "InstDTrans",
    "InstPrimaryTransformers",
    "InstSubstationTransformers",
    "InstTranLine",
    "InstTranVertices",
]

REGULATOR_TABLE_CANDIDATES = [
    "InstRegulators",
    "InstRegulator",
    "InstVoltageRegulators",
    "InstVoltageRegulator",
    "VoltageRegulators",
    "VoltageRegulator",
    "Regulators",
    "Regulator",
]

SOURCE_TABLE_CANDIDATES = [
    "InstFeeders",
    "Feeders",
    "Sources",
    "InstSources",
    "Source",
    "InstSource",
]


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


def find_transformer_table_names(table_names: list[str]) -> list[str]:
    lookup = {name.strip().lower(): name for name in table_names}
    matches: list[str] = []

    for candidate in TRANSFORMER_TABLE_CANDIDATES:
        match = lookup.get(candidate.lower())
        if match and match not in matches:
            matches.append(match)

    for table_name in table_names:
        normalized = table_name.lower()
        if (
            "transformer" in normalized
            or "xfmr" in normalized
            or "dtrans" in normalized
        ):
            if table_name not in matches:
                matches.append(table_name)

    return matches


def load_transformer_tables(connection, table_names: list[str]):
    transformer_table_names = find_transformer_table_names(table_names)
    frames = []

    for table_name in transformer_table_names:
        try:
            table = read_table(connection, table_name)
        except Exception as exc:
            print(f"Warning: found optional transformer table [{table_name}] but could not load it: {exc}")
            continue

        table = table.copy()
        table.insert(0, "TransformerSourceTable", table_name)
        frames.append(table)
        print(f"Transformer table loaded: {table_name} ({len(table)} rows)")

    if not frames:
        return None, transformer_table_names

    return pd.concat(frames, ignore_index=True, sort=False), transformer_table_names


def find_regulator_table_names(table_names: list[str]) -> list[str]:
    lookup = {name.strip().lower(): name for name in table_names}
    matches: list[str] = []

    for candidate in REGULATOR_TABLE_CANDIDATES:
        match = lookup.get(candidate.lower())
        if match and match not in matches:
            matches.append(match)

    for table_name in table_names:
        normalized = table_name.lower()
        if "regulator" in normalized or "voltagereg" in normalized:
            if table_name not in matches:
                matches.append(table_name)

    return matches


def load_regulator_tables(connection, table_names: list[str]):
    regulator_table_names = find_regulator_table_names(table_names)
    frames = []

    for table_name in regulator_table_names:
        try:
            table = read_table(connection, table_name)
        except Exception as exc:
            print(f"Warning: found optional regulator table [{table_name}] but could not load it: {exc}")
            continue

        table = table.copy()
        table.insert(0, "RegulatorSourceTable", table_name)
        frames.append(table)
        print(f"Regulator table loaded: {table_name} ({len(table)} rows)")

    if not frames:
        return None, regulator_table_names

    return pd.concat(frames, ignore_index=True, sort=False), regulator_table_names


def find_source_table_names(table_names: list[str]) -> list[str]:
    lookup = {name.strip().lower(): name for name in table_names}
    matches: list[str] = []

    for candidate in SOURCE_TABLE_CANDIDATES:
        match = lookup.get(candidate.lower())
        if match and match not in matches:
            matches.append(match)

    for table_name in table_names:
        normalized = table_name.lower()
        if "source" in normalized or normalized == "instfeeders":
            if table_name not in matches:
                matches.append(table_name)

    return matches


def load_source_tables(connection, table_names: list[str]):
    source_table_names = find_source_table_names(table_names)
    frames = []

    for table_name in source_table_names:
        try:
            table = read_table(connection, table_name)
        except Exception as exc:
            print(f"Warning: found optional source table [{table_name}] but could not load it: {exc}")
            continue

        table = table.copy()
        table.insert(0, "SourceTable", table_name)
        frames.append(table)
        print(f"Source table loaded: {table_name} ({len(table)} rows)")

    if not frames:
        return None, source_table_names

    return pd.concat(frames, ignore_index=True, sort=False), source_table_names


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

        print("\n========================")
        print("TABLES IN MDB")
        print("========================\n")

        user_tables = list(list_user_tables(conn))
        for table_name in user_tables:
            print(table_name)

        print("\n========================")
        print("LOADING TABLES")
        print("========================")

        nodes = load_table(conn, "Node")
        sections = load_table(conn, "InstSection")
        loads = load_table(conn, "Loads")
        capacitors = load_table(conn, "InstCapacitors")
        fuses = load_table(conn, "InstFuses")
        transformers, transformer_table_names = load_transformer_tables(conn, user_tables)
        regulators, regulator_table_names = load_regulator_tables(conn, user_tables)
        sources, source_table_names = load_source_tables(conn, user_tables)

        print(f"Nodes Loaded: {len(nodes)}")
        print(f"Sections Loaded: {len(sections)}")
        print(f"Loads Loaded: {len(loads)}")
        print(f"Capacitors Loaded: {len(capacitors)}")
        print(f"Fuses Loaded: {len(fuses)}")

        if transformers is None:
            print("Transformers Loaded: 0 - no transformer table found")
            if transformer_table_names:
                print("Transformer-like tables were found but none could be loaded:", transformer_table_names)
        else:
            print(f"Transformer tables detected: {transformer_table_names}")
            print(f"Transformer rows loaded total: {len(transformers)}")

        if regulators is None:
            print("Regulators Loaded: 0 - no regulator table found")
            if regulator_table_names:
                print("Regulator-like tables were found but none could be loaded:", regulator_table_names)
        else:
            print(f"Regulator tables detected: {regulator_table_names}")
            print(f"Regulator rows loaded total: {len(regulators)}")

        if sources is None:
            print("Sources Loaded: 0 - no source/feeder table found")
            if source_table_names:
                print("Source-like tables were found but none could be loaded:", source_table_names)
        else:
            print(f"Source tables detected: {source_table_names}")
            print(f"Source rows loaded total: {len(sources)}")

        print("\n========================")
        print("NODE COLUMNS")
        print("========================")
        print(nodes.columns.tolist())

        print("\n========================")
        print("SECTION COLUMNS")
        print("========================")
        print(sections.columns.tolist())

        missing_results = check_missing_data(sections)

        capacitor_results = check_capacitors(
            capacitors,
            sections,
            transformers=transformers,
            nodes=nodes,
        )

        regulator_results = check_regulators(
            regulators,
            sections,
            transformers=transformers,
            nodes=nodes,
        )

        source_voltage_results = check_source_voltage(
            sources,
        )

        fuse_results = check_open_fuses(
            fuses,
            sections,
        )

        height_results = check_conductor_height(
            sections,
        )

        load_results = check_connected_kva(
            loads,
            sections,
        )

        customer_count_results = check_customer_count(
            loads,
        )

        conductor_mismatch_results = check_conductor_mismatch(
            sections,
        )

        incorrect_phase_results = check_incorrect_phases(
            sections,
        )

        loop_results = check_loops(sections)
        unfed_topology_results = check_unfed_sections(sections)
        topology_results = {
            **loop_results,
            **unfed_topology_results,
        }

        print("\n========================")
        print("VALIDATION RESULTS")
        print("========================\n")

        print("Sections missing connectivity:", len(missing_results["missing_connectivity"]))
        print("Sections missing length:", len(missing_results["missing_length"]))
        print("Sections missing phase data:", len(missing_results["missing_phase"]))
        print("Sections missing conductor:", len(missing_results["missing_conductor"]))
        print("Duplicate Section IDs:", len(missing_results["duplicate_sections"]))
        print("Capacitor issues:", len(capacitor_results["capacitor_issues"]))
        print("Regulator issues:", len(regulator_results["regulator_issues"]))
        print("Source voltage issues:", len(source_voltage_results["source_voltage_issues"]))
        print("Open fuses:", len(fuse_results["open_fuses"]))
        print("Conductor height issues:", len(height_results["conductor_height_issues"]))
        print("Potential loop/meshed topology review sections:", len(loop_results["loop_sections"]))
        print("Topology cycle summary records:", len(loop_results["loop_summary"]))
        print("Topology cycle review records:", len(loop_results["loop_review_summary"]))
        print("Physical cycle diagnostic records:", len(loop_results["physical_cycle_diagnostics"]))

        if not loop_results["loop_diagnostics"].empty:
            print("\nLoop diagnostics:")
            for _, row in loop_results["loop_diagnostics"].iterrows():
                print(f"  {row['Check']}: {row['Count']}")

        print("Isolated topology component review sections:", len(unfed_topology_results["unfed_sections"]))
        print("Sections with load records but no connected load:", len(load_results["no_connected_kva"]))
        print("Customer count issues:", len(customer_count_results["customer_count_issues"]))
        print("Conductor configuration issues:", len(conductor_mismatch_results["conductor_issues"]))
        print("Incorrect phase issues:", len(incorrect_phase_results["incorrect_phases"]))

        write_validation_report(
            output_file,
            mdb_file,
            missing_results,
            capacitor_results,
            regulator_results,
            source_voltage_results,
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
