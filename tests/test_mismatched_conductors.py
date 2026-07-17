import pandas as pd

from checks.mismatched_conductors import check_conductor_mismatch


def _section(section_id, identical, c1, c2="Unknown", c3="Unknown"):
    return {
        "SectionId": section_id,
        "SectionPhases": "ABCN",
        "IdenticalPhaseConductors": identical,
        "PhaseConductorId": c1,
        "PhaseConductor2Id": c2,
        "PhaseConductor3Id": c3,
    }


def test_identical_phase_conductors_do_not_require_alternate_fields():
    sections = pd.DataFrame(
        [
            _section(
                "Ghm_00036",
                1,
                "15kV 350 Tape Shield",
            )
        ]
    )

    results = check_conductor_mismatch(sections)

    assert results["conductor_issues"].empty


def test_non_identical_phase_conductors_with_different_ids_are_reported():
    sections = pd.DataFrame(
        [
            _section(
                "S1",
                0,
                "336 ACSR",
                "1/0 ACSR",
                "336 ACSR",
            )
        ]
    )

    results = check_conductor_mismatch(sections)

    assert len(results["conductor_issues"]) == 1
    issue = results["conductor_issues"].iloc[0]
    assert issue["RuleID"] == "VR12"
    assert issue["ElementID"] == "S1"
    assert "differ" in issue["ConductorIssueDetail"]


def test_non_identical_phase_conductors_with_missing_active_field_are_reported():
    sections = pd.DataFrame(
        [
            _section(
                "S2",
                0,
                "336 ACSR",
                "Unknown",
                "336 ACSR",
            )
        ]
    )

    results = check_conductor_mismatch(sections)

    assert len(results["conductor_issues"]) == 1
    issue = results["conductor_issues"].iloc[0]
    assert issue["MissingConductorColumns"] == "PhaseConductor2Id"
