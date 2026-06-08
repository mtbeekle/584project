import pandas as pd

from validation_utils import add_issue_columns


def check_capacitors(capacitors, sections):

    results = {}

    print("\n========================")
    print("CAPACITOR COLUMNS")
    print("========================")

    print(capacitors.columns.tolist())

    # ==================================================
    # PHASE MISMATCH CHECK
    # ==================================================

    capacitor_phase_check = capacitors.merge(
        sections[['SectionId', 'SectionPhases']],
        on='SectionId',
        how='left'
    )

    phase_mismatch_rows = []

    for _, row in capacitor_phase_check.iterrows():

        cap_phases = str(row['ConnectedPhases']).upper()
        line_phases = str(row['SectionPhases']).upper()

        if not set(cap_phases).issubset(set(line_phases)):

            temp = row.copy()

            fixed_kvar = (
                row['FixedKvarPhase1'] +
                row['FixedKvarPhase2'] +
                row['FixedKvarPhase3']
            )

            switched_kvar = (
                row['Module1KvarPerPhase'] +
                row['Module2KvarPerPhase'] +
                row['Module3KvarPerPhase']
            )

            temp['TotalFixedKvar'] = fixed_kvar
            temp['TotalSwitchedKvar'] = switched_kvar
            temp['TotalKvar'] = fixed_kvar + switched_kvar
            temp['Issue'] = 'Phase Mismatch'

            phase_mismatch_rows.append(temp)

    phase_mismatches = add_issue_columns(
        pd.DataFrame(phase_mismatch_rows),
        rule_id="VR5",
        category="Component / Device",
        severity="Warning",
        element_type="Capacitor",
        element_id="UniqueDeviceId",
        issue="Phase mismatch",
        description=(
            "Capacitor connected phases are not a subset of the associated section phases."
        ),
        recommended_action=(
            "Review ConnectedPhases and the linked section SectionPhases values."
        ),
    )

    # ==================================================
    # BUILD GENERAL QA TABLE
    # ==================================================

    capacitor_issue_rows = []

    for _, row in capacitors.iterrows():

        fixed_kvar = (
            row['FixedKvarPhase1'] +
            row['FixedKvarPhase2'] +
            row['FixedKvarPhase3']
        )

        switched_kvar = (
            row['Module1KvarPerPhase'] +
            row['Module2KvarPerPhase'] +
            row['Module3KvarPerPhase']
        )

        total_kvar = fixed_kvar + switched_kvar

        issues = []

        # ----------------------------------------------
        # No kvar configured
        # ----------------------------------------------

        if fixed_kvar == 0 and switched_kvar == 0:
            issues.append("No KVAR")

        # ----------------------------------------------
        # Capacitor > 1 MVAR
        # ----------------------------------------------

        if total_kvar > 1000:
            issues.append(">1 MVAR")

        if issues:

            temp = row.copy()

            temp['TotalFixedKvar'] = fixed_kvar
            temp['TotalSwitchedKvar'] = switched_kvar
            temp['TotalKvar'] = total_kvar
            temp['Issue'] = "; ".join(issues)

            capacitor_issue_rows.append(temp)

    capacitor_issues = add_issue_columns(
        pd.DataFrame(capacitor_issue_rows),
        rule_id="VR5",
        category="Component / Device",
        severity="Warning",
        element_type="Capacitor",
        element_id="UniqueDeviceId",
        description="Capacitor configuration is outside expected validation limits.",
        recommended_action=(
            "Review capacitor KVAR settings and confirm the converted model values."
        ),
    )

    # ==================================================
    # COMBINE ALL ISSUES
    # ==================================================

    if not phase_mismatches.empty:

        capacitor_issues = pd.concat(
            [
                capacitor_issues,
                phase_mismatches
            ],
            ignore_index=True
        )

    results['capacitor_issues'] = capacitor_issues

    # ==================================================
    # SUMMARY
    # ==================================================

    print("\n========================")
    print("CAPACITOR SUMMARY")
    print("========================")

    print(
        f"Total capacitor issues found: "
        f"{len(capacitor_issues)}"
    )

    return results
