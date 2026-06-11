import pandas as pd

from rules import get_rule
from validation_utils import validate_required_columns, add_rule_columns


PHASE_KVA_COLUMNS = [
    "Phase1Kva",
    "Phase2Kva",
    "Phase3Kva",
]

PHASE_KW_COLUMNS = [
    "Phase1Kw",
    "Phase2Kw",
    "Phase3Kw",
]

PHASE_KVAR_COLUMNS = [
    "Phase1Kvar",
    "Phase2Kvar",
    "Phase3Kvar",
]

KVA_COLUMN_CANDIDATES = [
    "ConnectedKva",
    "ConnectedKVA",
    "Connected_kVA",
    "LoadKva",
    "LoadKVA",
    "Kva",
    "KVA",
    "BillingKva",
    "BillingKVA",
]


PHASE_POWER_COLUMN_GROUPS = {
    "KVA": PHASE_KVA_COLUMNS,
    "KW": PHASE_KW_COLUMNS,
    "KVAR": PHASE_KVAR_COLUMNS,
}


def find_phase_power_column_groups(loads: pd.DataFrame) -> dict[str, list[str]]:
    return {
        unit: columns
        for unit, columns in PHASE_POWER_COLUMN_GROUPS.items()
        if all(column in loads.columns for column in columns)
    }


def find_total_kva_columns(loads: pd.DataFrame) -> list[str]:
    return [
        column
        for column in KVA_COLUMN_CANDIDATES
        if column in loads.columns
    ]


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
    total_kva_columns = [] if phase_power_column_groups else find_total_kva_columns(loads)

    if not phase_power_column_groups and not total_kva_columns:
        checked_columns = (
            PHASE_KVA_COLUMNS +
            PHASE_KW_COLUMNS +
            PHASE_KVAR_COLUMNS +
            KVA_COLUMN_CANDIDATES
        )
        raise ValueError(
            "loads is missing a recognized connected load power column. "
            f"Checked: {', '.join(checked_columns)}"
        )

    load_values = loads.copy()
    load_total_columns = []
    section_total_columns = []
    issue_basis_columns = []

    for unit, columns in phase_power_column_groups.items():
        for column in columns:
            load_values[column] = pd.to_numeric(
                load_values[column],
                errors="coerce"
            ).fillna(0)

        total_column = f"TotalConnected{unit}"
        load_values[total_column] = load_values[columns].sum(axis=1)
        load_total_columns.append(total_column)

        section_total_column = f"Section{total_column}"
        load_values[section_total_column] = (
            load_values.groupby("SectionId")[total_column].transform("sum")
        )
        section_total_columns.append(section_total_column)
        if unit == "KVA":
            issue_basis_columns.append(section_total_column)

    if total_kva_columns:
        for column in total_kva_columns:
            load_values[column] = pd.to_numeric(
                load_values[column],
                errors="coerce"
            ).fillna(0)

        load_values["TotalConnectedKVA"] = load_values[total_kva_columns].sum(axis=1)
        load_total_columns.append("TotalConnectedKVA")

        section_total_column = "SectionTotalConnectedKVA"
        load_values[section_total_column] = (
            load_values.groupby("SectionId")["TotalConnectedKVA"].transform("sum")
        )
        section_total_columns.append(section_total_column)
        issue_basis_columns.append(section_total_column)

    if not issue_basis_columns:
        issue_basis_columns = section_total_columns

    section_load_summary = (
        load_values
        .groupby("SectionId", as_index=False)
        .agg(
            LoadRecordCount=("SectionId", "size"),
            **{
                column: (column, "first")
                for column in section_total_columns
            }
        )
    )

    no_connected_kva = add_rule_columns(
        section_load_summary[
            (section_load_summary[issue_basis_columns] <= 0).all(axis=1)
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
    print(f"Issue basis columns used: {issue_basis_columns}")
    print(f"Sections with load records but no connected load: {len(no_connected_kva)}")

    return results
