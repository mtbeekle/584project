import pandas as pd


PHASE_KVA_COLUMNS = [
    "Phase1Kva",
    "Phase2Kva",
    "Phase3Kva",
    "Phase1kva",
    "Phase2kva",
    "Phase3kva",
]

PHASE_KW_COLUMNS = [
    "Phase1Kw",
    "Phase2Kw",
    "Phase3Kw",
    "LoadPhase1Kw",
    "LoadPhase2Kw",
    "LoadPhase3Kw",
]

PHASE_KVAR_COLUMNS = [
    "Phase1Kvar",
    "Phase2Kvar",
    "Phase3Kvar",
    "LoadPhase1Kvar",
    "LoadPhase2Kvar",
    "LoadPhase3Kvar",
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

TOTAL_KW_COLUMN_CANDIDATES = [
    "TotalKw",
    "TotalKW",
    "ConnectedKw",
    "ConnectedKW",
    "LoadKw",
    "LoadKW",
]

TOTAL_KVAR_COLUMN_CANDIDATES = [
    "TotalKvar",
    "TotalKVAR",
    "ConnectedKvar",
    "ConnectedKVAR",
    "LoadKvar",
    "LoadKVAR",
]


PHASE_POWER_COLUMN_GROUPS = {
    "KVA": [
        ["Phase1Kva", "Phase1kva"],
        ["Phase2Kva", "Phase2kva"],
        ["Phase3Kva", "Phase3kva"],
    ],
    "KW": [
        ["Phase1Kw", "LoadPhase1Kw"],
        ["Phase2Kw", "LoadPhase2Kw"],
        ["Phase3Kw", "LoadPhase3Kw"],
    ],
    "KVAR": [
        ["Phase1Kvar", "LoadPhase1Kvar"],
        ["Phase2Kvar", "LoadPhase2Kvar"],
        ["Phase3Kvar", "LoadPhase3Kvar"],
    ],
}


def numeric_sum(dataframe: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series(0.0, index=dataframe.index)

    numeric_values = dataframe[columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    return numeric_values.sum(axis=1)


def _column_lookup(dataframe: pd.DataFrame) -> dict[str, list[str]]:
    lookup = {}
    for column in dataframe.columns:
        lookup.setdefault(str(column).strip().lower(), []).append(column)
    return lookup


def _find_existing_columns(dataframe: pd.DataFrame, candidates: list[str]) -> list[str]:
    lookup = _column_lookup(dataframe)
    columns = []
    for candidate in candidates:
        for column in lookup.get(candidate.lower(), []):
            if column not in columns and dataframe[column].notna().any():
                columns.append(column)
    return columns


def find_phase_power_column_groups(loads: pd.DataFrame) -> dict[str, list[str]]:
    groups = {}
    for unit, phase_candidates in PHASE_POWER_COLUMN_GROUPS.items():
        columns = []
        for candidates in phase_candidates:
            matched = _find_existing_columns(loads, candidates)
            if not matched:
                columns = []
                break
            columns.extend(matched)
        if columns:
            groups[unit] = columns
    return groups


def find_total_kva_columns(loads: pd.DataFrame) -> list[str]:
    return _find_existing_columns(loads, KVA_COLUMN_CANDIDATES)


def find_total_kw_columns(loads: pd.DataFrame) -> list[str]:
    return _find_existing_columns(loads, TOTAL_KW_COLUMN_CANDIDATES)


def find_total_kvar_columns(loads: pd.DataFrame) -> list[str]:
    return _find_existing_columns(loads, TOTAL_KVAR_COLUMN_CANDIDATES)


def checked_power_columns() -> list[str]:
    return (
        PHASE_KVA_COLUMNS
        + PHASE_KW_COLUMNS
        + PHASE_KVAR_COLUMNS
        + KVA_COLUMN_CANDIDATES
        + TOTAL_KW_COLUMN_CANDIDATES
        + TOTAL_KVAR_COLUMN_CANDIDATES
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
