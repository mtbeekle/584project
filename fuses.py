import pandas as pd


def check_open_fuses(fuses, sections):

    results = {}

    print("\n========================")
    print("FUSE COLUMNS")
    print("========================")

    print(fuses.columns.tolist())

    # ==========================================
    # OPEN FUSES
    # ==========================================

    open_fuses = fuses[
        fuses['FuseIsOpen'] == True
    ]

    results['open_fuses'] = open_fuses

    # ==========================================
    # UNFED SECTIONS
    # ==========================================

    unfed_sections = sections[
        sections['IsFed'] == False
    ]

    results['unfed_sections'] = unfed_sections

    # ==========================================
    # OPEN FUSE SECTIONS
    # ==========================================

    open_fuse_section_ids = set(
        open_fuses['SectionId']
    )

    # Sections that contain open fuses
    open_fuse_sections = sections[
        sections['SectionId'].isin(open_fuse_section_ids)
    ]

    results['open_fuse_sections'] = open_fuse_sections

    # ==========================================
    # OPEN FUSE + UNFED
    # ==========================================

    unfed_due_to_open_fuse = unfed_sections[
        unfed_sections['SectionId'].isin(open_fuse_section_ids)
    ]

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
