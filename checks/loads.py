import pandas as pd

from rules import get_rule
from validation_utils import validate_required_columns, add_rule_columns
from checks.load_power import (
    checked_power_columns,
    find_phase_power_column_groups,
    find_total_kvar_columns,
    find_total_kva_columns,
    find_total_kw_columns,
    numeric_sum,
)


def _annotate_load_group(loads: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    phase_power_column_groups = find_phase_power_column_groups(loads)
    total_kva_columns = find_total_kva_columns(loads)
    total_kw_columns = find_total_kw_columns(loads)
    total_kvar_columns = find_total_kvar_columns(loads)

    if (
        not phase_power_column_groups
        and not total_kva_columns
        and not total_kw_columns
        and not total_kvar_columns
    ):
        raise ValueError(
            "loads is missing a recognized connected load power column. "
            f"Checked: {', '.join(checked_power_columns())}"
        )

    load_values = loads.copy()
    load_values["TotalConnectedKVAForCheck"] = 0.0
    load_values["ConnectedLoadBasis"] = ""

    if "KVA" in phase_power_column_groups:
        load_values["TotalConnectedKVA"] = numeric_sum(load_values, phase_power_column_groups["KVA"])
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVA"]
        basis = "phase KVA"
    elif total_kva_columns:
        load_values["TotalConnectedKVA"] = numeric_sum(load_values, total_kva_columns)
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVA"]
        basis = "total KVA"
    elif "KW" in phase_power_column_groups and "KVAR" in phase_power_column_groups:
        load_values["TotalConnectedKW"] = numeric_sum(load_values, phase_power_column_groups["KW"])
        load_values["TotalConnectedKVAR"] = numeric_sum(load_values, phase_power_column_groups["KVAR"])
        load_values["TotalConnectedKVAForCheck"] = (
            load_values["TotalConnectedKW"].pow(2)
            + load_values["TotalConnectedKVAR"].pow(2)
        ).pow(0.5)
        basis = "sqrt(KW^2 + KVAR^2)"
    elif total_kw_columns and total_kvar_columns:
        load_values["TotalConnectedKW"] = numeric_sum(load_values, total_kw_columns)
        load_values["TotalConnectedKVAR"] = numeric_sum(load_values, total_kvar_columns)
        load_values["TotalConnectedKVAForCheck"] = (
            load_values["TotalConnectedKW"].pow(2)
            + load_values["TotalConnectedKVAR"].pow(2)
        ).pow(0.5)
        basis = "sqrt(total KW^2 + total KVAR^2)"
    elif "KW" in phase_power_column_groups:
        load_values["TotalConnectedKW"] = numeric_sum(load_values, phase_power_column_groups["KW"])
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKW"].abs()
        basis = "absolute KW proxy"
    elif total_kw_columns:
        load_values["TotalConnectedKW"] = numeric_sum(load_values, total_kw_columns)
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKW"].abs()
        basis = "absolute total KW proxy"
    elif "KVAR" in phase_power_column_groups:
        load_values["TotalConnectedKVAR"] = numeric_sum(load_values, phase_power_column_groups["KVAR"])
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVAR"].abs()
        basis = "absolute KVAR proxy"
    else:
        load_values["TotalConnectedKVAR"] = numeric_sum(load_values, total_kvar_columns)
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVAR"].abs()
        basis = "absolute total KVAR proxy"

    load_values["ConnectedLoadBasis"] = basis
    diagnostics = {
        "phase_power_column_groups": phase_power_column_groups,
        "total_kva_columns": total_kva_columns,
        "total_kw_columns": total_kw_columns,
        "total_kvar_columns": total_kvar_columns,
        "basis": basis,
    }
    return load_values, diagnostics


def check_connected_kva(loads: pd.DataFrame, sections: pd.DataFrame) -> dict:
    results = {}

    validate_required_columns(
        loads,
        "loads",
        ["SectionId"]
    )

    validate_required_columns(
        sections,
        "sections",
        ["SectionId"]
    )

    annotated_groups = []
    diagnostics = []
    if "LoadSourceTable" in loads.columns:
        load_groups = loads.groupby("LoadSourceTable", dropna=False, sort=False)
    else:
        load_groups = [(None, loads)]
    for source_table, load_group in load_groups:
        annotated, diagnostic = _annotate_load_group(load_group)
        diagnostic["source_table"] = source_table
        annotated_groups.append(annotated)
        diagnostics.append(diagnostic)

    load_values = pd.concat(annotated_groups, ignore_index=True, sort=False)
    total_columns = [
        column
        for column in ["TotalConnectedKVA", "TotalConnectedKW", "TotalConnectedKVAR"]
        if column in load_values.columns
    ]
    for column in total_columns:
        load_values[column] = pd.to_numeric(load_values[column], errors="coerce").fillna(0)

    section_load_summary = (
        load_values
        .groupby("SectionId", as_index=False)
        .agg(
            LoadRecordCount=("SectionId", "size"),
            LoadSourceTables=(
                "LoadSourceTable",
                lambda values: ", ".join(sorted({str(value) for value in values.dropna()})),
            ) if "LoadSourceTable" in load_values.columns else ("SectionId", lambda values: "Loads"),
            ConnectedLoadBasis=(
                "ConnectedLoadBasis",
                lambda values: ", ".join(sorted({str(value) for value in values.dropna()})),
            ),
            SectionTotalConnectedKVAForCheck=("TotalConnectedKVAForCheck", "sum"),
            **{
                f"Section{column}": (column, "sum")
                for column in total_columns
            }
        )
    )

    no_connected_kva = add_rule_columns(
        section_load_summary[
            section_load_summary["SectionTotalConnectedKVAForCheck"] <= 0
        ],
        rule=get_rule("VR10"),
        element_type="Section",
        element_id="SectionId",
    )

    results["no_connected_kva"] = no_connected_kva

    print("\n========================")
    print("LOAD SUMMARY")
    print("========================")
    for diagnostic in diagnostics:
        source_table = diagnostic["source_table"] or "Loads"
        print(f"Load source {source_table}: basis={diagnostic['basis']}")
        print(f"  phase power columns: {diagnostic['phase_power_column_groups']}")
        print(f"  total kVA columns: {diagnostic['total_kva_columns']}")
        print(f"  total kW columns: {diagnostic['total_kw_columns']}")
        print(f"  total kVAR columns: {diagnostic['total_kvar_columns']}")
    print(f"Load-bearing sections evaluated: {len(section_load_summary)}")
    print(f"Load-bearing sections with no connected load: {len(no_connected_kva)}")

    return results
