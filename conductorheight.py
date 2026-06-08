import pandas as pd

from validation_utils import add_issue_columns


def check_conductor_height(sections):

    results = {}

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
    conductor_height_issues = add_issue_columns(
        conductor_height_issues,
        rule_id="VR6",
        category="Component / Device",
        severity="Warning",
        element_type="Section",
        element_id="SectionId",
        description=(
            "Conductor height sign does not match the inferred underground or overhead conductor type."
        ),
        recommended_action=(
            "Review PhaseConductorId and AveHeightAboveGround_MUL for the section."
        ),
    )

    results['conductor_height_issues'] = (
        conductor_height_issues
    )

    print(
        f"Conductor height issues found: "
        f"{len(conductor_height_issues)}"
    )

    return results
