import pandas as pd


def check_missing_data(sections):

    results = {}

    # =========================
    # Missing connectivity
    # =========================

    missing_connectivity = sections[
        sections['FromNodeId'].isna() |
        sections['ToNodeId'].isna()
    ]

    results['missing_connectivity'] = missing_connectivity

    # =========================
    # Missing section length
    # =========================

    missing_length = sections[
        sections['SectionLength_MUL'].isna() |
        (sections['SectionLength_MUL'] <= 0)
    ]

    results['missing_length'] = missing_length

    # =========================
    # Missing phase data
    # =========================

    missing_phase = sections[
        sections['SectionPhases'].isna()
    ]

    results['missing_phase'] = missing_phase

    # =========================
    # Missing conductor
    # =========================

    missing_conductor = sections[
        sections['PhaseConductorId'].isna()
    ]

    results['missing_conductor'] = missing_conductor

    # =========================
    # Duplicate Section IDs
    # =========================

    duplicate_sections = sections[
        sections.duplicated(
            subset=['SectionId'],
            keep=False
        )
    ]

    results['duplicate_sections'] = duplicate_sections

    return results
