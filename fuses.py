import pandas as pd

from rules import get_rule
from validation_utils import (
    validate_required_columns,
    is_true_series,
    is_false_series,
    add_rule_columns,
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

    open_fuses = add_rule_columns(
        fuses[is_true_series(fuses["FuseIsOpen"])],
        rule=get_rule("VR4"),
        element_type="Fuse",
        element_id="UniqueDeviceId",
    )

    results['open_fuses'] = open_fuses

    # ==========================================
    # UNFED SECTIONS
    # ==========================================
    # Preliminary VR1 topology check using MDB IsFed, not a full graph traversal.

    unfed_sections = add_rule_columns(
        sections[is_false_series(sections["IsFed"])],
        rule=get_rule("VR1"),
        element_type="Section",
        element_id="SectionId",
    )

    results['unfed_sections'] = unfed_sections

    # ==========================================
    # OPEN FUSE SECTIONS
    # ==========================================

    open_fuse_section_ids = set(
        open_fuses['SectionId']
    )

    # Sections that contain open fuses
    open_fuse_sections = add_rule_columns(
        sections[sections['SectionId'].isin(open_fuse_section_ids)],
        rule=get_rule("VR4"),
        element_type="Section",
        element_id="SectionId",
    )

    results['open_fuse_sections'] = open_fuse_sections

    # ==========================================
    # OPEN FUSE + UNFED
    # ==========================================

    unfed_due_to_open_fuse = add_rule_columns(
        unfed_sections[unfed_sections['SectionId'].isin(open_fuse_section_ids)],
        rule=get_rule("VR1"),
        element_type="Section",
        element_id="SectionId",
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
