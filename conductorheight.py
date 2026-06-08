import pandas as pd

from rules import get_rule
from validation_utils import add_rule_columns, validate_required_columns


def check_conductor_height(sections):

    results = {}

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "PhaseConductorId", "AveHeightAboveGround_MUL"],
    )

    print("\n========================")
    print("CONDUCTOR HEIGHT CHECK")
    print("========================")

    ug_keywords = [
        "CONC",
        "NEUT",
        "TAPE",
        "SHIELD",
        "XLP",
        "XLPE",
        "SEP"
    ]

    issue_rows = []

    for _, row in sections.iterrows():

        conductor = str(row['PhaseConductorId']).upper()
        height = row['AveHeightAboveGround_MUL']

        if pd.isna(height):
            continue

        is_ug = any(
            keyword in conductor
            for keyword in ug_keywords
        )

        issue = None

        # ==========================================
        # UNDERGROUND CONDUCTORS
        # Must have negative height
        # ==========================================

        if is_ug and height >= 0:

            issue = (
                "UG Conductor Height Should Be Negative"
            )

        # ==========================================
        # OVERHEAD CONDUCTORS
        # Must have positive height
        # ==========================================

        elif not is_ug and height <= 0:

            issue = (
                "OH Conductor Height Should Be Positive"
            )

        if issue:

            temp = row.copy()

            temp['Issue'] = issue

            issue_rows.append(temp)

    conductor_height_issues = pd.DataFrame(issue_rows)
    conductor_height_issues = add_rule_columns(
        conductor_height_issues,
        rule=get_rule("VR11"),
        element_type="Section",
        element_id="SectionId",
    )

    results['conductor_height_issues'] = (
        conductor_height_issues
    )

    print(
        f"Conductor height issues found: "
        f"{len(conductor_height_issues)}"
    )

    return results
