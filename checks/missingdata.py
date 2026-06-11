#import pandas as pd

from validation_utils import add_issue_columns, validate_required_columns


def check_missing_data(sections):

    results = {}

    validate_required_columns(
        sections,
        "sections",
        [
            "SectionId",
            "FromNodeId",
            "ToNodeId",
            "SectionLength_MUL",
            "SectionPhases",
            "PhaseConductorId",
        ],
    )

    # =========================
    # Missing connectivity
    # =========================

    missing_connectivity = add_issue_columns(
        sections[
            sections['FromNodeId'].isna() |
            sections['ToNodeId'].isna()
        ],
        rule_id="",
        category="Data Quality",
        severity="Error",
        element_type="Section",
        element_id="SectionId",
        issue="Missing connectivity",
        description="Section is missing a from-node or to-node reference.",
        recommended_action=(
            "Populate both FromNodeId and ToNodeId with valid connected node IDs."
        ),
    )

    results['missing_connectivity'] = missing_connectivity

    # =========================
    # Missing section length
    # =========================

    missing_length = add_issue_columns(
        sections[
            sections['SectionLength_MUL'].isna() |
            (sections['SectionLength_MUL'] <= 0)
        ],
        rule_id="",
        category="Data Quality",
        severity="Error",
        element_type="Section",
        element_id="SectionId",
        issue="Missing or invalid section length",
        description="Section length is missing, zero, or negative.",
        recommended_action="Populate SectionLength_MUL with a valid positive length.",
    )

    results['missing_length'] = missing_length

    # =========================
    # Missing phase data
    # =========================

    missing_phase = add_issue_columns(
        sections[
            sections['SectionPhases'].isna()
        ],
        rule_id="",
        category="Data Quality",
        severity="Error",
        element_type="Section",
        element_id="SectionId",
        issue="Missing phase data",
        description="Section phase data is missing.",
        recommended_action="Populate SectionPhases with the expected phase designation.",
    )

    results['missing_phase'] = missing_phase

    # =========================
    # Missing conductor
    # =========================

    missing_conductor = add_issue_columns(
        sections[
            sections['PhaseConductorId'].isna()
        ],
        rule_id="",
        category="Data Quality",
        severity="Warning",
        element_type="Section",
        element_id="SectionId",
        issue="Missing conductor",
        description="Section phase conductor ID is missing.",
        recommended_action="Populate PhaseConductorId with the expected conductor ID.",
    )

    results['missing_conductor'] = missing_conductor

    # =========================
    # Duplicate Section IDs
    # =========================

    duplicate_sections = add_issue_columns(
        sections[
            sections.duplicated(
                subset=['SectionId'],
                keep=False
            )
        ],
        rule_id="",
        category="Data Integrity",
        severity="Error",
        element_type="Section",
        element_id="SectionId",
        issue="Duplicate section ID",
        description="More than one section record uses the same SectionId.",
        recommended_action="Review duplicated SectionId values and make each section unique.",
    )

    results['duplicate_sections'] = duplicate_sections

    return results
