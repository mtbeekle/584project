import pandas as pd

from validation_utils import (
    validate_required_columns,
    is_true_series,
    is_false_series,
    add_issue_columns,
)


def check_open_fuses(fuses: pd.DataFrame, sections: pd.DataFrame) -> dict:

    results = {}

    validate_required_columns(
        fuses,
        "fuses",
        ["FuseIsOpen", "SectionId"]
    )
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "IsFed"]
    )

    print("\n========================")
    print("FUSE COLUMNS")
    print("========================")

    print(fuses.columns.tolist())

    # ==========================================
    # OPEN FUSES
    # ==========================================
    # Implements charter rule VR4 for open protective devices.

    open_fuses = add_issue_columns(
        fuses[is_true_series(fuses["FuseIsOpen"])],
        rule_id="VR4",
        category="Component / Device",
        severity="Warning",
        issue="Open fuse",
        description="Fuse is open in converted model; review device status.",
        recommended_action=(
            "Confirm whether the fuse should be open in the normal converted model."
        ),
    )

    results['open_fuses'] = open_fuses

    # ==========================================
    # UNFED SECTIONS
    # ==========================================
    # Preliminary VR1 topology check using MDB IsFed, not a full graph traversal.

    unfed_sections = add_issue_columns(
        sections[is_false_series(sections["IsFed"])],
        rule_id="VR1",
        category="Topology",
        severity="Error",
        issue="Unfed section",
        description="Section is marked unfed or disconnected from a valid source path.",
        recommended_action=(
            "Review upstream connectivity, source path, and switching/fuse status."
        ),
    )

    results['unfed_sections'] = unfed_sections

    # ==========================================
    # OPEN FUSE SECTIONS
    # ==========================================

    open_fuse_section_ids = set(
        open_fuses['SectionId']
    )

    # Sections that contain open fuses
    open_fuse_sections = add_issue_columns(
        sections[sections['SectionId'].isin(open_fuse_section_ids)],
        rule_id="VR4",
        category="Component / Device",
        severity="Warning",
        issue="Section contains open fuse",
        description="Section contains a fuse marked open in the converted model.",
        recommended_action=(
            "Review the fuse status and confirm whether the connected section "
            "should be energized in the normal converted model."
        ),
    )

    results['open_fuse_sections'] = open_fuse_sections

    # ==========================================
    # OPEN FUSE + UNFED
    # ==========================================

    unfed_due_to_open_fuse = add_issue_columns(
        unfed_sections[unfed_sections['SectionId'].isin(open_fuse_section_ids)],
        rule_id="VR1/VR4",
        category="Topology",
        severity="Error",
        issue="Unfed section contains open fuse",
        description=(
            "Section is marked unfed and contains a fuse marked open in the converted model."
        ),
        recommended_action=(
            "Review whether the open fuse is causing the section to appear unfed, "
            "or whether there is an additional upstream connectivity issue."
        ),
    )

    results['unfed_due_to_open_fuse'] = unfed_due_to_open_fuse

    # ==========================================
    # SUMMARY
    # ==========================================

    print("\n========================")
    print("FUSE SUMMARY")
    print("========================")

    print(f"Open Fuses: {len(open_fuses)}")
    print(f"Unfed Sections: {len(unfed_sections)}")
    print(f"Open Fuse Sections: {len(open_fuse_sections)}")
    print(f"Open Fuse + Unfed: {len(unfed_due_to_open_fuse)}")

    return results
