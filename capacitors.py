import pandas as pd

from rules import get_rule
from validation_utils import add_issue_columns, add_rule_columns


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

    phase_mismatches = add_rule_columns(
        pd.DataFrame(phase_mismatch_rows),
        rule=get_rule("VR7"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    # ==================================================
    # BUILD GENERAL QA TABLE
    # ==================================================

    capacitor_rating_issue_rows = []
    capacitor_high_mvar_issue_rows = []

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

        # ----------------------------------------------
        # No kvar configured
        # ----------------------------------------------

        if fixed_kvar == 0 and switched_kvar == 0:
            temp = row.copy()

            temp['TotalFixedKvar'] = fixed_kvar
            temp['TotalSwitchedKvar'] = switched_kvar
            temp['TotalKvar'] = total_kvar

            capacitor_rating_issue_rows.append(temp)

        # ----------------------------------------------
        # Capacitor > 1 MVAR
        # ----------------------------------------------

        if total_kvar > 1000:
            temp = row.copy()

            temp['TotalFixedKvar'] = fixed_kvar
            temp['TotalSwitchedKvar'] = switched_kvar
            temp['TotalKvar'] = total_kvar

            capacitor_high_mvar_issue_rows.append(temp)

    capacitor_rating_issues = add_rule_columns(
        pd.DataFrame(capacitor_rating_issue_rows),
        rule=get_rule("VR5"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    capacitor_high_mvar_issues = add_issue_columns(
        pd.DataFrame(capacitor_high_mvar_issue_rows),
        rule_id="",
        category="Component / Device",
        severity="Warning",
        element_type="Capacitor",
        element_id="UniqueDeviceId",
        issue="Capacitor greater than 1 MVAR",
        description="Capacitor configured rating is greater than 1 MVAR.",
        recommended_action=(
            "Review capacitor KVAR settings and confirm the converted model values."
        ),
    )

    capacitor_issues = pd.concat(
        [
            capacitor_rating_issues,
            capacitor_high_mvar_issues,
        ],
        ignore_index=True
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
