from pathlib import Path

import pandas as pd


STANDARD_ISSUE_COLUMNS = [
    "SourceSheet",
    "RuleID",
    "Category",
    "Severity",
    "ElementType",
    "ElementID",
    "Issue",
    "Description",
    "RecommendedAction",
]


def build_issues_log(report_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    issue_frames = []

    for sheet_name, dataframe in report_tables.items():
        if dataframe.empty:
            continue

        issue_frame = dataframe.copy()
        issue_frame.insert(0, "SourceSheet", sheet_name)
        issue_frames.append(issue_frame)

    if not issue_frames:
        return pd.DataFrame(
            columns=STANDARD_ISSUE_COLUMNS
        )

    issues = pd.concat(issue_frames, ignore_index=True, sort=False)
    ordered_columns = [
        column
        for column in STANDARD_ISSUE_COLUMNS
        if column in issues.columns
    ]
    remaining_columns = [
        column
        for column in issues.columns
        if column not in ordered_columns
    ]

    return issues[ordered_columns + remaining_columns]


def build_report_tables(
    missing_results: dict[str, pd.DataFrame],
    capacitor_results: dict[str, pd.DataFrame],
    fuse_results: dict[str, pd.DataFrame],
    height_results: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    report_tables = {
        "MissingConnectivity": missing_results["missing_connectivity"],
        "MissingLength": missing_results["missing_length"],
        "MissingPhase": missing_results["missing_phase"],
        "MissingConductor": missing_results["missing_conductor"],
        "DuplicateSections": missing_results["duplicate_sections"],
        "CapacitorIssues": capacitor_results["capacitor_issues"],
        "OpenFuses": fuse_results["open_fuses"],
        "UnfedSections": fuse_results["unfed_sections"],
        "ConductorHeight": height_results["conductor_height_issues"],
    }

    summary_rows = [
        {"Check": sheet_name, "Count": len(dataframe)}
        for sheet_name, dataframe in report_tables.items()
    ]
    summary = pd.DataFrame(summary_rows)

    issues = build_issues_log(report_tables)

    return {
        "Summary": summary,
        "Issues": issues,
        **report_tables,
    }


def write_validation_report(
    output_file: Path,
    missing_results: dict[str, pd.DataFrame],
    capacitor_results: dict[str, pd.DataFrame],
    fuse_results: dict[str, pd.DataFrame],
    height_results: dict[str, pd.DataFrame],
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_tables = build_report_tables(
        missing_results,
        capacitor_results,
        fuse_results,
        height_results,
    )

    with pd.ExcelWriter(output_file) as writer:
        for sheet_name, dataframe in report_tables.items():
            dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
