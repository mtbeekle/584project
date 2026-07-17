import pandas as pd

from rules import get_rule
from validation_utils import validate_required_columns, add_rule_columns
from checks.load_power import (
    checked_power_columns,
    find_phase_power_column_groups,
    find_total_kva_columns,
    numeric_sum,
)


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

    phase_power_column_groups = find_phase_power_column_groups(loads)
    total_kva_columns = find_total_kva_columns(loads)

    if not phase_power_column_groups and not total_kva_columns:
        raise ValueError(
            "loads is missing a recognized connected load power column. "
            f"Checked: {', '.join(checked_power_columns())}"
        )

    load_values = loads.copy()
    load_total_columns = []
    load_values["TotalConnectedKVAForCheck"] = 0.0
    load_basis_parts = []

    if "KVA" in phase_power_column_groups:
        load_values["TotalConnectedKVA"] = numeric_sum(load_values, phase_power_column_groups["KVA"])
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVA"]
        load_total_columns.append("TotalConnectedKVA")
        load_basis_parts.append("phase KVA")
    elif total_kva_columns:
        load_values["TotalConnectedKVA"] = numeric_sum(load_values, total_kva_columns)
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVA"]
        load_total_columns.append("TotalConnectedKVA")
        load_basis_parts.append("total KVA")
    elif "KW" in phase_power_column_groups and "KVAR" in phase_power_column_groups:
        load_values["TotalConnectedKW"] = numeric_sum(load_values, phase_power_column_groups["KW"])
        load_values["TotalConnectedKVAR"] = numeric_sum(load_values, phase_power_column_groups["KVAR"])
        load_values["TotalConnectedKVAForCheck"] = (
            load_values["TotalConnectedKW"].pow(2)
            + load_values["TotalConnectedKVAR"].pow(2)
        ).pow(0.5)
        load_total_columns.extend(["TotalConnectedKW", "TotalConnectedKVAR"])
        load_basis_parts.append("sqrt(KW^2 + KVAR^2)")
    elif "KW" in phase_power_column_groups:
        load_values["TotalConnectedKW"] = numeric_sum(load_values, phase_power_column_groups["KW"])
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKW"].abs()
        load_total_columns.append("TotalConnectedKW")
        load_basis_parts.append("absolute KW proxy")
    elif "KVAR" in phase_power_column_groups:
        load_values["TotalConnectedKVAR"] = numeric_sum(load_values, phase_power_column_groups["KVAR"])
        load_values["TotalConnectedKVAForCheck"] = load_values["TotalConnectedKVAR"].abs()
        load_total_columns.append("TotalConnectedKVAR")
        load_basis_parts.append("absolute KVAR proxy")

    load_total_columns.append("TotalConnectedKVAForCheck")

    section_load_summary = (
        load_values
        .groupby("SectionId", as_index=False)
        .agg(
            LoadRecordCount=("SectionId", "size"),
            **{
                column: (column, "first")
                for column in load_total_columns
            }
        )
    )
    section_load_summary = section_load_summary.rename(
        columns={
            column: f"Section{column}"
            for column in load_total_columns
        }
    )

    section_load_summary = sections[["SectionId"]].drop_duplicates().merge(
        section_load_summary,
        on="SectionId",
        how="left",
    )
    section_load_summary["LoadRecordCount"] = section_load_summary["LoadRecordCount"].fillna(0).astype(int)
    for column in section_load_summary.columns:
        if column.startswith("SectionTotalConnected"):
            section_load_summary[column] = section_load_summary[column].fillna(0)
    section_load_summary["ConnectedLoadBasis"] = ", ".join(load_basis_parts)

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
    print(f"Phase power column groups used: {phase_power_column_groups}")
    print(f"Total kVA columns used: {total_kva_columns}")
    print(f"Connected load basis used: {', '.join(load_basis_parts)}")
    print(f"Sections with no connected load: {len(no_connected_kva)}")

    return results
