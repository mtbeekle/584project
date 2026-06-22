import pandas as pd

from rules import get_rule
from validation_utils import add_rule_columns, validate_required_columns


LOAD_KW_COLUMNS = [
    "Phase1Kw",
    "Phase2Kw",
    "Phase3Kw",
]

CUSTOMER_COUNT_COLUMNS = [
    "Phase1Customers",
    "Phase2Customers",
    "Phase3Customers",
]


def check_customer_count(loads: pd.DataFrame) -> dict:
    results = {}

    validate_required_columns(
        loads,
        "loads",
        ["SectionId"] + LOAD_KW_COLUMNS + CUSTOMER_COUNT_COLUMNS,
    )

    print("\n========================")
    print("CUSTOMER COUNT CHECK")
    print("========================")

    load_values = loads.copy()

    for column in LOAD_KW_COLUMNS + CUSTOMER_COUNT_COLUMNS:
        load_values[column] = pd.to_numeric(
            load_values[column],
            errors="coerce",
        )

    load_values["TotalPhaseKwForCheck"] = load_values[LOAD_KW_COLUMNS].fillna(0).sum(axis=1)
    load_values["TotalCustomerCountForCheck"] = (
        load_values[CUSTOMER_COUNT_COLUMNS].fillna(0).sum(axis=1)
    )

    issue_rows = load_values[
        (load_values["TotalPhaseKwForCheck"] > 0)
        & (load_values["TotalCustomerCountForCheck"] <= 0)
    ].copy()

    customer_count_issues = add_rule_columns(
        issue_rows,
        rule=get_rule("VR14"),
        element_type="Load",
        element_id="SectionId",
    )

    results["customer_count_issues"] = customer_count_issues

    print(f"Customer count issues found: {len(customer_count_issues)}")

    return results
