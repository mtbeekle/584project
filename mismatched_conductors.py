import pandas as pd
#VR12 Mismatched conductors

def check_conductor_mismatch(sections):

    results = {}

    print("\n========================")
    print("CONDUCTOR CONFIGURATION CHECK")
    print("========================")

    issue_rows = []

    for _, row in sections.iterrows():

        phases = str(row['SectionPhases']).strip()

        # ==========================================
        # ONLY CHECK 3-PHASE SECTIONS
        # ==========================================

        if phases != "ABCN":
            continue

        use_equiv = row.get("UseEquivSpacing", 0)

        conductor1 = str(row['PhaseConductorId']).strip()
        conductor2 = str(row['PhaseConductor2Id']).strip()
        conductor3 = str(row['PhaseConductor3Id']).strip()

        issue = None

        # ==========================================
        # EQUIVALENT SPACING
        # ==========================================

        if use_equiv == 1:

            if (
                conductor1 == "Unknown"
                or pd.isna(row['PhaseConductorId'])
            ):
                issue = (
                    "Equivalent spacing section "
                    "missing PhaseConductorId"
                )

        # ==========================================
        # FULL CONDUCTOR MODEL
        # ==========================================

        else:

            if (
                conductor1 == "Unknown"
                or conductor2 == "Unknown"
                or conductor3 == "Unknown"
            ):
                issue = (
                    "Non-equivalent spacing section "
                    "missing phase conductor assignment"
                )

        if issue:

            temp = row.copy()

            temp["Issue"] = issue

            issue_rows.append(temp)

    conductor_issues = pd.DataFrame(issue_rows)

    results["conductor_issues"] = conductor_issues

    print(
        f"Conductor configuration issues found: "
        f"{len(conductor_issues)}"
    )

    return results