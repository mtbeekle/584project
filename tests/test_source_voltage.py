import pandas as pd

from checks.source_voltage import check_source_voltage


def test_source_voltage_mismatch_is_reported():
    sources = pd.DataFrame(
        [
            {
                "FeederId": "F1",
                "NominalKvll": 12.47,
                "BusVoltageLevel": 4.16,
            }
        ]
    )

    results = check_source_voltage(sources)

    assert len(results["source_voltage_issues"]) == 1
    issue = results["source_voltage_issues"].iloc[0]
    assert issue["RuleID"] == "VR3"
    assert issue["ElementID"] == "F1"
    assert issue["Severity"] == "Error"
    assert issue["VR3VoltageStatus"] == "VR3 source voltage mismatch"


def test_source_voltage_pass_goes_to_context_only():
    sources = pd.DataFrame(
        [
            {
                "FeederId": "F1",
                "NominalKvll": 12.47,
                "BusVoltageLevel": 12.5,
            }
        ]
    )

    results = check_source_voltage(sources)

    assert results["source_voltage_issues"].empty
    assert results["source_voltage_context"]["VR3VoltageStatus"].tolist() == [
        "VR3 voltage pass"
    ]


def test_source_voltage_missing_expected_voltage_is_diagnostic_only():
    sources = pd.DataFrame(
        [
            {
                "FeederId": "F1",
                "NominalKvll": 12.47,
            }
        ]
    )

    results = check_source_voltage(sources)

    assert results["source_voltage_issues"].empty
    assert results["source_voltage_context"].iloc[0]["VR3VoltageStatus"] == (
        "Cannot run VR3: expected feeder/system voltage is missing, zero, or unreadable"
    )
