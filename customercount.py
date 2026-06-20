import pandas as pd


def check_customer_count(loads):

    results = {}

    print("\n========================")
    print("CUSTOMER COUNT CHECK")
    print("========================")

    issue_rows = loads[
        (
            (loads['Phase1Kw'] > 0) |
            (loads['Phase2Kw'] > 0) |
            (loads['Phase3Kw'] > 0)
        )
        &
        (loads['Phase1Customers'] == 0)
        &
        (loads['Phase2Customers'] == 0)
        &
        (loads['Phase3Customers'] == 0)
    ].copy()

    issue_rows["RuleID"] = "LOAD001"
    issue_rows["Category"] = "Load Data"
    issue_rows["Severity"] = "Medium"
    issue_rows["ElementType"] = "Load"
    issue_rows["ElementID"] = issue_rows["SectionId"]
    issue_rows["Issue"] = (
        "Load present with zero customers"
    )
    issue_rows["Description"] = (
        "Connected load exists but all customer counts "
        "are zero."
    )
    issue_rows["RecommendedAction"] = (
        "Review whether customer counts are missing "
        "or intentionally set to zero."
    )

    results["customer_count_issues"] = issue_rows

    print(
        f"Customer count issues found: "
        f"{len(issue_rows)}"
    )

    return results