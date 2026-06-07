from pathlib import Path

import pandas as pd


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

    issues = summary[summary["Count"] > 0].copy()
    if issues.empty:
        issues = pd.DataFrame(
            [{"Check": "No validation issues found", "Count": 0}]
        )

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
    
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file) as writer:
        for sheet_name, dataframe in report_tables.items():
            dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
