import pandas as pd


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


def numeric_sum(dataframe: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series(0.0, index=dataframe.index)

    numeric_values = dataframe[columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    return numeric_values.sum(axis=1)


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


def checked_power_columns() -> list[str]:
    return (
        PHASE_KVA_COLUMNS
        + PHASE_KW_COLUMNS
        + PHASE_KVAR_COLUMNS
        + KVA_COLUMN_CANDIDATES
    )


def choose_preferred_load_basis(loads: pd.DataFrame) -> tuple[str, list[str]]:
    phase_power_column_groups = find_phase_power_column_groups(loads)

    if "KVA" in phase_power_column_groups:
        return "KVA", phase_power_column_groups["KVA"]

    non_kva_units = [
        unit
        for unit in ("KW", "KVAR")
        if unit in phase_power_column_groups
    ]
    if non_kva_units:
        load_basis_columns = [
            column
            for unit in non_kva_units
            for column in phase_power_column_groups[unit]
        ]
        return "+".join(non_kva_units), load_basis_columns

    total_kva_columns = find_total_kva_columns(loads)
    if total_kva_columns:
        return "KVA", total_kva_columns

    raise ValueError(
        "loads is missing a recognized connected load power column. "
        f"Checked: {', '.join(checked_power_columns())}"
    )
