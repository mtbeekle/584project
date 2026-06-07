import pandas as pd


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

    results['conductor_height_issues'] = (
        conductor_height_issues
    )

    print(
        f"Conductor height issues found: "
        f"{len(conductor_height_issues)}"
    )

    return results