import pandas as pd


def phase_count(phase_string):

    phase_string = str(phase_string)

    count = 0

    if "A" in phase_string:
        count += 1

    if "B" in phase_string:
        count += 1

    if "C" in phase_string:
        count += 1

    return count


def check_incorrect_phases(sections):

    print("\n========================")
    print("INCORRECT PHASE CHECK")
    print("========================")

    issues = []

    for _, upstream in sections.iterrows():

        downstream_sections = sections[
            sections["FromNodeId"] ==
            upstream["ToNodeId"]
        ]

        upstream_phase_count = phase_count(
            upstream["SectionPhases"]
        )

        for _, downstream in downstream_sections.iterrows():

            downstream_phase_count = phase_count(
                downstream["SectionPhases"]
            )

            if downstream_phase_count > upstream_phase_count:

                issues.append({
                    "RuleID":
                        "PHASE001",

                    "Category":
                        "Connectivity",

                    "Severity":
                        "Medium",

                    "ElementType":
                        "Section",

                    "ElementID":
                        downstream["SectionId"],

                    "Issue":
                        "Downstream section has more phases than upstream section",

                    "Description":
                        (
                            f"Upstream section "
                            f"{upstream['SectionId']} "
                            f"({upstream['SectionPhases']}) "
                            f"feeds downstream section "
                            f"{downstream['SectionId']} "
                            f"({downstream['SectionPhases']})."
                        ),

                    "RecommendedAction":
                        (
                            "Verify phase designations "
                            "and any intervening devices."
                        ),

                    "UpstreamSection":
                        upstream["SectionId"],

                    "UpstreamPhases":
                        upstream["SectionPhases"],

                    "DownstreamSection":
                        downstream["SectionId"],

                    "DownstreamPhases":
                        downstream["SectionPhases"],

                    "FromNode":
                        downstream["FromNodeId"]
                })

    issue_df = pd.DataFrame(issues)

    print(
        f"Potential incorrect phase issues found: "
        f"{len(issue_df)}"
    )

    return {
        "incorrect_phases": issue_df
    }