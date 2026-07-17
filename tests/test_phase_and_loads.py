import pandas as pd

from checks.loads import check_connected_kva
from validation_utils import parse_phase_set


def test_parse_phase_set_supports_synergi_numeric_bitmasks():
    assert parse_phase_set(1) == {"A"}
    assert parse_phase_set(2) == {"B"}
    assert parse_phase_set(4) == {"C"}
    assert parse_phase_set(5) == {"A", "C"}
    assert parse_phase_set(6) == {"B", "C"}
    assert parse_phase_set(7) == {"A", "B", "C"}


def test_connected_kva_does_not_flag_sections_without_load_records():
    sections = pd.DataFrame(
        {
            "SectionId": ["S1", "S2"],
        }
    )
    loads = pd.DataFrame(
        {
            "SectionId": ["S1"],
            "Phase1Kva": [10],
            "Phase2Kva": [0],
            "Phase3Kva": [0],
        }
    )

    results = check_connected_kva(loads, sections)

    assert results["no_connected_kva"].empty


def test_connected_kva_flags_load_records_with_zero_kva():
    sections = pd.DataFrame(
        {
            "SectionId": ["S1", "S2"],
        }
    )
    loads = pd.DataFrame(
        {
            "SectionId": ["S1", "S2"],
            "Phase1Kva": [10, 0],
            "Phase2Kva": [0, 0],
            "Phase3Kva": [0, 0],
        }
    )

    results = check_connected_kva(loads, sections)

    assert results["no_connected_kva"]["SectionId"].tolist() == ["S2"]
    assert results["no_connected_kva"].iloc[0]["LoadRecordCount"] == 1


def test_connected_kva_derives_apparent_power_from_kw_and_kvar():
    sections = pd.DataFrame(
        {
            "SectionId": ["S1", "S2"],
        }
    )
    loads = pd.DataFrame(
        {
            "SectionId": ["S1", "S2"],
            "Phase1Kw": [3, 0],
            "Phase2Kw": [0, 0],
            "Phase3Kw": [0, 0],
            "Phase1Kvar": [4, 0],
            "Phase2Kvar": [0, 0],
            "Phase3Kvar": [0, 0],
        }
    )

    results = check_connected_kva(loads, sections)

    assert results["no_connected_kva"]["SectionId"].tolist() == ["S2"]
