import numpy as np
import pandas as pd

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    clean_column_names,
    parse_phase_set,
    validate_required_columns,
)


VR6_VOLTAGE_TOLERANCE_PCT = 10.0
CAPACITOR_RATED_KV_COLUMNS = [
    "RatedKv",
    "RatedKV",
    "Rated kV",
    "Rated_kV",
    "RatedKvLL",
    "RatedKVLL",
]
SECTION_VOLTAGE_COLUMNS = [
    "SectionNominalKv",
    "NominalKv",
    "NominalKV",
    "NominalVoltage",
    "BaseKv",
    "BaseKV",
    "BaseVoltage",
    "OperatingKv",
    "Voltage",
    "Kv",
    "KV",
]


def _key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "")


def _find_col(dataframe: pd.DataFrame, names: list[str]) -> str | None:
    lookup = {_key(column): column for column in dataframe.columns}
    for name in names:
        matched = lookup.get(_key(name))
        if matched:
            return matched
    return None


def _num(value: object) -> float:
    if value is None:
        return np.nan

    try:
        if pd.isna(value):
            return np.nan
    except Exception:
        pass

    normalized = str(value).strip()
    if normalized == "":
        return np.nan

    normalized = normalized.replace(",", "")
    for unit in ["kV", "KV", "kv", "V"]:
        normalized = normalized.replace(unit, "")

    try:
        return float(normalized.strip())
    except Exception:
        return np.nan


def _voltage_kv(value: object) -> float:
    numeric_value = _num(value)
    if pd.isna(numeric_value):
        return np.nan

    return numeric_value / 1000.0 if abs(numeric_value) > 1000 else numeric_value


def _section_context_column(
    source_column: str,
    capacitors: pd.DataFrame,
    context: pd.DataFrame,
) -> str:
    suffixed_column = f"{source_column}_Section"
    if source_column in capacitors.columns and suffixed_column in context.columns:
        return suffixed_column

    return source_column


def _is_active(value: object) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    if isinstance(value, bool):
        return value

    return str(value).strip().upper() in {
        "1",
        "TRUE",
        "T",
        "YES",
        "Y",
        "ON",
        "ACTIVE",
        "ENABLED",
        "CLOSED",
    }


def _fixed_kvar(row: pd.Series) -> float:
    total = 0.0
    for column in ["FixedKvarPhase1", "FixedKvarPhase2", "FixedKvarPhase3"]:
        if column not in row.index:
            continue

        value = _num(row[column])
        if not pd.isna(value):
            total += value

    return total


def _module_kvar_per_phase(row: pd.Series) -> float:
    total = 0.0
    for index in range(1, 10):
        kvar_column = f"Module{index}KvarPerPhase"
        active_column = f"Module{index}Activated"

        if kvar_column not in row.index:
            continue

        kvar_value = _num(row[kvar_column])
        if pd.isna(kvar_value):
            kvar_value = 0.0

        if active_column in row.index:
            if _is_active(row[active_column]):
                total += kvar_value
        else:
            total += kvar_value

    return total


def _build_capacitor_totals(row: pd.Series) -> dict[str, float]:
    fixed_kvar = _fixed_kvar(row)
    module_kvar_per_phase = _module_kvar_per_phase(row)
    connected_phases = (
        parse_phase_set(row["ConnectedPhases"])
        if "ConnectedPhases" in row.index
        else set()
    )
    switched_phase_count = len(connected_phases) if connected_phases else 3
    switched_kvar = module_kvar_per_phase * switched_phase_count
    return {
        "TotalFixedKvar": fixed_kvar,
        "TotalModuleKvarPerPhase": module_kvar_per_phase,
        "TotalSwitchedPhaseCount": switched_phase_count,
        "TotalSwitchedKvar": switched_kvar,
        "TotalKvar": fixed_kvar + switched_kvar,
    }


def check_capacitors(capacitors, sections):
    capacitors = clean_column_names(capacitors)
    sections = clean_column_names(sections)

    results = {}

    validate_required_columns(
        capacitors,
        "capacitors",
        [
            "SectionId",
            "UniqueDeviceId",
            "ConnectedPhases",
            "FixedKvarPhase1",
            "FixedKvarPhase2",
            "FixedKvarPhase3",
        ],
    )
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "SectionPhases"],
    )

    print("\n========================")
    print("CAPACITOR COLUMNS")
    print("========================")
    print(capacitors.columns.tolist())

    rated_kv_column = _find_col(capacitors, CAPACITOR_RATED_KV_COLUMNS)
    print("RatedKv column used:", rated_kv_column)

    capacitor_phase_check = capacitors.merge(
        sections,
        on="SectionId",
        how="left",
        suffixes=("", "_Section"),
    )

    section_voltage_source_column = _find_col(sections, SECTION_VOLTAGE_COLUMNS)
    section_voltage_column = (
        _section_context_column(
            section_voltage_source_column,
            capacitors,
            capacitor_phase_check,
        )
        if section_voltage_source_column
        else None
    )

    print("Section voltage column used:", section_voltage_column)

    # ==================================================
    # VR7: PHASE MISMATCH CHECK
    # ==================================================

    phase_mismatch_rows = []

    for _, row in capacitor_phase_check.iterrows():
        cap_phases = parse_phase_set(row["ConnectedPhases"])
        line_phases = parse_phase_set(row["SectionPhases"])

        if cap_phases and line_phases and not cap_phases.issubset(line_phases):
            temp = row.copy()
            temp["CapacitorPhasesForCheck"] = "".join(sorted(cap_phases))
            temp["SectionPhasesForCheck"] = "".join(sorted(line_phases))
            for key, value in _build_capacitor_totals(row).items():
                temp[key] = value
            phase_mismatch_rows.append(temp)

    phase_mismatches = add_rule_columns(
        pd.DataFrame(phase_mismatch_rows),
        rule=get_rule("VR7"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    # ==================================================
    # VR5: ZERO OR MISSING KVAR RATING
    # ==================================================

    capacitor_rating_issue_rows = []

    for _, row in capacitors.iterrows():
        totals = _build_capacitor_totals(row)
        if totals["TotalFixedKvar"] > 0 or totals["TotalModuleKvarPerPhase"] > 0:
            continue

        temp = row.copy()
        for key, value in totals.items():
            temp[key] = value
        capacitor_rating_issue_rows.append(temp)

    capacitor_rating_issues = add_rule_columns(
        pd.DataFrame(capacitor_rating_issue_rows),
        rule=get_rule("VR5"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    # ==================================================
    # VR6 subissue: MISSING OR ZERO RATEDKV
    # ==================================================

    capacitor_missing_rated_kv_rows = []

    if rated_kv_column:
        for _, row in capacitors.iterrows():
            rated_kv_numeric = _num(row[rated_kv_column])
            if not pd.isna(rated_kv_numeric) and rated_kv_numeric > 0:
                continue

            temp = row.copy()
            temp["RatedKvColumnUsed"] = rated_kv_column
            temp["RatedKvRaw"] = row[rated_kv_column]
            temp["RatedKvNumeric"] = rated_kv_numeric
            for key, value in _build_capacitor_totals(row).items():
                temp[key] = value
            capacitor_missing_rated_kv_rows.append(temp)

    capacitor_missing_rated_kv_issues = add_rule_columns(
        pd.DataFrame(capacitor_missing_rated_kv_rows),
        rule=get_rule("VR6"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    if not capacitor_missing_rated_kv_issues.empty:
        capacitor_missing_rated_kv_issues["Severity"] = "Review"
        capacitor_missing_rated_kv_issues["Issue"] = "Capacitor RatedKv is missing or zero"
        capacitor_missing_rated_kv_issues["Description"] = (
            "Capacitor RatedKv is blank, missing, or zero in the source data."
        )
        capacitor_missing_rated_kv_issues["RecommendedAction"] = (
            "Check the RatedKv column for this capacitor and populate a valid kV value if needed."
        )

    # ==================================================
    # VR6: VOLTAGE MISMATCH
    # ==================================================

    capacitor_voltage_issue_rows = []

    if rated_kv_column and section_voltage_column:
        for _, row in capacitor_phase_check.iterrows():
            capacitor_kv = _voltage_kv(row[rated_kv_column])
            section_kv = _voltage_kv(row[section_voltage_column])

            if (
                pd.isna(capacitor_kv)
                or capacitor_kv <= 0
                or pd.isna(section_kv)
                or section_kv <= 0
            ):
                continue

            percent_difference = abs(capacitor_kv - section_kv) / section_kv * 100
            if percent_difference <= VR6_VOLTAGE_TOLERANCE_PCT:
                continue

            temp = row.copy()
            temp["CapacitorRatedKvForCheck"] = capacitor_kv
            temp["SectionVoltageKvForCheck"] = section_kv
            temp["VoltagePercentDifference"] = percent_difference
            temp["SectionVoltageColumnUsed"] = section_voltage_column
            for key, value in _build_capacitor_totals(row).items():
                temp[key] = value
            capacitor_voltage_issue_rows.append(temp)

    capacitor_voltage_issues = add_rule_columns(
        pd.DataFrame(capacitor_voltage_issue_rows),
        rule=get_rule("VR6"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    capacitor_issues = pd.concat(
        [
            capacitor_rating_issues,
            capacitor_missing_rated_kv_issues,
            capacitor_voltage_issues,
            phase_mismatches,
        ],
        ignore_index=True,
    )

    results["capacitor_issues"] = capacitor_issues

    print("\n========================")
    print("CAPACITOR SUMMARY")
    print("========================")
    print("VR5 zero or missing kVAR rating:", len(capacitor_rating_issues))
    print("VR6 missing or zero RatedKv:", len(capacitor_missing_rated_kv_issues))
    print("VR6 voltage mismatch:", len(capacitor_voltage_issues))
    print("VR7 phase mismatch:", len(phase_mismatches))
    print(f"Total capacitor issues found: {len(capacitor_issues)}")

    return results
