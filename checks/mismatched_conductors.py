import pandas as pd

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    normalize_boolean_value,
    parse_phase_set,
    validate_required_columns,
)


CONDUCTOR_COLUMNS = [
    "PhaseConductorId",
    "PhaseConductor2Id",
    "PhaseConductor3Id",
]
PHASE_TO_CONDUCTOR_COLUMN = {
    "A": "PhaseConductorId",
    "B": "PhaseConductor2Id",
    "C": "PhaseConductor3Id",
}


def _is_missing_conductor(value: object) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    normalized = str(value).strip()
    return normalized == "" or normalized.upper() == "UNKNOWN"


def _normalize_conductor(value: object) -> str:
    if _is_missing_conductor(value):
        return ""
    return str(value).strip().upper()


def check_conductor_mismatch(sections: pd.DataFrame) -> dict:
    results = {}

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "SectionPhases", "IdenticalPhaseConductors"] + CONDUCTOR_COLUMNS,
    )

    print("\n========================")
    print("CONDUCTOR CONFIGURATION CHECK")
    print("========================")

    issue_rows = []

    for _, row in sections.iterrows():
        phases = parse_phase_set(row["SectionPhases"])

        if not phases:
            continue

        identical_phase_conductors = normalize_boolean_value(row["IdenticalPhaseConductors"])

        # When Synergi states phase conductors are identical, alternate phase
        # conductor fields may be Unknown without indicating a mixed conductor.
        if identical_phase_conductors is not False:
            continue

        active_columns = [
            PHASE_TO_CONDUCTOR_COLUMN[phase]
            for phase in sorted(phases)
            if phase in PHASE_TO_CONDUCTOR_COLUMN
        ]
        if len(active_columns) < 2:
            continue

        missing_columns = [
            column
            for column in active_columns
            if _is_missing_conductor(row[column])
        ]
        conductor_values = {
            column: _normalize_conductor(row[column])
            for column in active_columns
            if not _is_missing_conductor(row[column])
        }
        has_different_conductors = len(set(conductor_values.values())) > 1

        if not missing_columns and not has_different_conductors:
            continue

        issue_row = row.copy()
        issue_row["ConductorIssueDetail"] = (
            "Section is marked as using non-identical phase conductors, but one or more active phase conductor fields are missing"
            if missing_columns
            else "Section is marked as using non-identical phase conductors and active phase conductor IDs differ"
        )
        issue_row["IdenticalPhaseConductorsForCheck"] = row["IdenticalPhaseConductors"]
        issue_row["ActivePhaseConductorColumns"] = ", ".join(active_columns)
        issue_row["PhaseConductorsForCheck"] = "; ".join(
            f"{column}={row[column]}" for column in active_columns
        )
        issue_row["MissingConductorColumns"] = ", ".join(missing_columns)
        issue_rows.append(issue_row)

    conductor_issues = add_rule_columns(
        pd.DataFrame(issue_rows),
        rule=get_rule("VR12"),
        element_type="Section",
        element_id="SectionId",
    )

    results["conductor_issues"] = conductor_issues

    print(f"Conductor configuration issues found: {len(conductor_issues)}")

    return results
