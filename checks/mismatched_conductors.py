import pandas as pd

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    parse_phase_set,
    validate_required_columns,
)


CONDUCTOR_COLUMNS = [
    "PhaseConductorId",
    "PhaseConductor2Id",
    "PhaseConductor3Id",
]


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


def _uses_equivalent_spacing(value: object) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    if isinstance(value, bool):
        return value

    return str(value).strip().upper() in {"1", "TRUE", "T", "YES", "Y"}


def check_conductor_mismatch(sections: pd.DataFrame) -> dict:
    results = {}

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "SectionPhases", "UseEquivSpacing"] + CONDUCTOR_COLUMNS,
    )

    print("\n========================")
    print("CONDUCTOR CONFIGURATION CHECK")
    print("========================")

    issue_rows = []

    for _, row in sections.iterrows():
        phases = parse_phase_set(row["SectionPhases"])

        if phases != {"A", "B", "C"}:
            continue

        use_equiv = _uses_equivalent_spacing(row["UseEquivSpacing"])
        conductor_values = {
            column: row[column]
            for column in CONDUCTOR_COLUMNS
        }

        if use_equiv:
            missing_columns = [
                "PhaseConductorId"
                if _is_missing_conductor(row["PhaseConductorId"])
                else None
            ]
        else:
            missing_columns = [
                column
                for column, value in conductor_values.items()
                if _is_missing_conductor(value)
            ]

        missing_columns = [column for column in missing_columns if column]

        if not missing_columns:
            continue

        issue_row = row.copy()
        issue_row["ConductorIssueDetail"] = (
            "Equivalent spacing section missing PhaseConductorId"
            if use_equiv
            else "Non-equivalent spacing section missing phase conductor assignment"
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
