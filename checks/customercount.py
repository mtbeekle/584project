import pandas as pd

from checks.load_power import choose_preferred_load_basis
from rules import get_rule
from validation_utils import add_rule_columns, is_true_series, validate_required_columns

CUSTOMER_COUNT_COLUMNS = [
    "Phase1Customers",
    "Phase2Customers",
    "Phase3Customers",
]


def check_customer_count(loads: pd.DataFrame) -> dict:
    results = {}
    load_basis_unit, load_basis_columns = choose_preferred_load_basis(loads)

    validate_required_columns(
        loads,
        "loads",
        ["SectionId"] + load_basis_columns + CUSTOMER_COUNT_COLUMNS,
    )

    print("\n========================")
    print("CUSTOMER COUNT CHECK")
    print("========================")

    load_values = loads.copy()

    for column in load_basis_columns + CUSTOMER_COUNT_COLUMNS:
        load_values[column] = pd.to_numeric(
            load_values[column],
            errors="coerce",
        )

    total_load_column = f"TotalCustomerCountCheck{load_basis_unit}"
    load_values[total_load_column] = (
        load_values[load_basis_columns].fillna(0).sum(axis=1)
    )
    load_values["TotalCustomerCountForCheck"] = (
        load_values[CUSTOMER_COUNT_COLUMNS].fillna(0).sum(axis=1)
    )
    load_values["CustomerCountLoadBasis"] = load_basis_unit

    if "IsSpotLoad" in load_values.columns:
        spot_load_mask = is_true_series(load_values["IsSpotLoad"])
    else:
        spot_load_mask = pd.Series(False, index=load_values.index)

    issue_rows = load_values[
        (~spot_load_mask)
        & (load_values[total_load_column] > 0)
        & (load_values["TotalCustomerCountForCheck"] <= 0)
    ].copy()

    customer_count_issues = add_rule_columns(
        issue_rows,
        rule=get_rule("VR14"),
        element_type="Load",
        element_id="SectionId",
    )

    results["customer_count_issues"] = customer_count_issues

    print(f"Load basis used: {load_basis_unit} ({load_basis_columns})")
    print(f"Spot load records skipped: {int(spot_load_mask.sum())}")
    print(f"Customer count issues found: {len(customer_count_issues)}")

    return results
