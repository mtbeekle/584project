import pandas as pd


TRUE_VALUES = {
    True,
    1,
    -1,
    "1",
    "-1",
    "true",
    "t",
    "yes",
    "y",
    "open",
    "on",
}

FALSE_VALUES = {
    False,
    0,
    "0",
    "false",
    "f",
    "no",
    "n",
    "closed",
    "off",
}


def validate_required_columns(
    dataframe: pd.DataFrame,
    dataframe_name: str,
    required_columns: list[str],
) -> None:
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        missing_list = ", ".join(missing_columns)
        raise ValueError(
            f"{dataframe_name} is missing required column(s): {missing_list}"
        )


def normalize_boolean_value(value) -> bool | None:
    if pd.isna(value):
        return None

    if isinstance(value, str):
        normalized_value = value.strip().lower()
    else:
        normalized_value = value

    if normalized_value in TRUE_VALUES:
        return True

    if normalized_value in FALSE_VALUES:
        return False

    return None


def is_true_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_boolean_value).eq(True)


def is_false_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_boolean_value).eq(False)


def add_issue_columns(
    dataframe: pd.DataFrame,
    rule_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    issue: str | None = None,
    description: str | None = None,
    recommended_action: str | None = None,
) -> pd.DataFrame:
    issue_dataframe = dataframe.copy()

    if rule_id is not None:
        issue_dataframe["RuleID"] = rule_id
    if category is not None:
        issue_dataframe["Category"] = category
    if severity is not None:
        issue_dataframe["Severity"] = severity
    if issue is not None:
        issue_dataframe["Issue"] = issue
    if description is not None:
        issue_dataframe["Description"] = description
    if recommended_action is not None:
        issue_dataframe["RecommendedAction"] = recommended_action

    return issue_dataframe


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
        issue="Section contains open fuse",
    )

    results['open_fuse_sections'] = open_fuse_sections

    # ==========================================
    # OPEN FUSE + UNFED
    # ==========================================

    unfed_due_to_open_fuse = add_issue_columns(
        unfed_sections[unfed_sections['SectionId'].isin(open_fuse_section_ids)],
        issue="Unfed section contains open fuse",
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
