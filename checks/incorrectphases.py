import pandas as pd

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    parse_phase_set,
    validate_required_columns,
)


def check_incorrect_phases(sections: pd.DataFrame) -> dict:
    results = {}

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId", "SectionPhases"],
    )

    print("\n========================")
    print("INCORRECT PHASE CHECK")
    print("========================")

    issue_rows = []

    for _, upstream in sections.iterrows():
        downstream_sections = sections[
            sections["FromNodeId"] == upstream["ToNodeId"]
        ]
        upstream_phases = parse_phase_set(upstream["SectionPhases"])

        for _, downstream in downstream_sections.iterrows():
            downstream_phases = parse_phase_set(downstream["SectionPhases"])

            if not upstream_phases or not downstream_phases:
                continue

            if not downstream_phases.issubset(upstream_phases):
                issue_row = downstream.copy()
                issue_row["UpstreamSection"] = upstream["SectionId"]
                issue_row["UpstreamPhases"] = upstream["SectionPhases"]
                issue_row["UpstreamPhaseCount"] = len(upstream_phases)
                issue_row["DownstreamSection"] = downstream["SectionId"]
                issue_row["DownstreamPhases"] = downstream["SectionPhases"]
                issue_row["DownstreamPhaseCount"] = len(downstream_phases)
                issue_row["FromNode"] = downstream["FromNodeId"]
                issue_rows.append(issue_row)

    incorrect_phases = add_rule_columns(
        pd.DataFrame(issue_rows),
        rule=get_rule("VR13"),
        element_type="Section",
        element_id="SectionId",
    )

    results["incorrect_phases"] = incorrect_phases

    print(f"Potential incorrect phase issues found: {len(incorrect_phases)}")

    return results
