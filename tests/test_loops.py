import pandas as pd
import networkx as nx

from topology.graph_builder import build_section_graph
from topology.loops import (
    CLOSED,
    UNKNOWN,
    check_loops,
    filter_closed_sections,
    find_loop_section_ids,
)


def _sections(rows):
    return pd.DataFrame(rows)


def _closed_section(section_id, from_node, to_node, feeder="F1", phases="ABC", **extra):
    row = {
        "SectionId": section_id,
        "FromNodeId": from_node,
        "ToNodeId": to_node,
        "FeederId": feeder,
        "SectionPhases": phases,
        "IsFromEndOpen": False,
        "IsToEndOpen": False,
    }
    row.update(extra)
    return row


def test_multigraph_preserves_parallel_sections_as_separate_edges():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "A", "B"),
        ]
    )

    graph = build_section_graph(sections)

    assert graph.number_of_edges() == 2
    assert sorted(data["SectionId"] for _, _, data in graph.edges(data=True)) == ["S1", "S2"]


def test_find_loop_section_ids_handles_graph_and_multigraph_edge_data():
    graph = nx.Graph()
    graph.add_edge("A", "B", SectionId="S1")
    graph.add_edge("B", "C", SectionId="S2")
    graph.add_edge("C", "A", SectionId="S3")

    multigraph = nx.MultiGraph()
    multigraph.add_edge("A", "B", key="S1", SectionId="S1")
    multigraph.add_edge("B", "C", key="S2", SectionId="S2")
    multigraph.add_edge("C", "A", key="S3", SectionId="S3")

    assert find_loop_section_ids(graph) == {"S1", "S2", "S3"}
    assert find_loop_section_ids(multigraph) == {"S1", "S2", "S3"}


def test_radial_feeder_has_no_loop_findings():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "D"),
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert results["loop_sections"].empty


def test_open_tie_physical_ring_is_absent_from_loop_summary():
    open_tie = _closed_section("TIE", "C", "A")
    open_tie["IsFromEndOpen"] = True
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
            open_tie,
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert results["loop_review_summary"].empty
    assert results["loop_sections"].empty
    assert len(results["physical_cycle_diagnostics"]) == 1
    assert results["physical_cycle_diagnostics"].iloc[0]["OpenSectionCount"] == 1


def test_confirmed_closed_radial_cycle_is_error():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "A"),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "RADIAL"})

    assert len(results["loop_summary"]) == 1
    assert results["loop_summary"]["Severity"].tolist() == ["Error"]
    assert results["loop_review_summary"].empty
    assert set(results["loop_section_details"]["SectionId"]) == {"S1", "S2", "S3"}
    assert results["loop_section_details"]["Severity"].unique().tolist() == ["Error"]
    assert results["loop_review_section_details"].empty


def test_closed_cross_feeder_tie_cycle_is_warning():
    sections = _sections(
        [
            _closed_section("S1", "A", "B", feeder="F1"),
            _closed_section("S2", "B", "C", feeder="F1"),
            _closed_section("TIE", "C", "A", feeder="F2"),
        ]
    )

    results = check_loops(sections)

    assert len(results["loop_summary"]) == 1
    assert results["loop_summary"]["Severity"].tolist() == ["Warning"]
    assert "multiple feeders" in results["loop_summary"].iloc[0]["LikelyCause"]


def test_duplicate_section_ids_are_reported_separately():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S1", "B", "C"),
            _closed_section("S2", "C", "D"),
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert len(results["topology_duplicate_section_ids"]) == 2


def test_self_loops_are_reported_separately_and_excluded_from_graph_cycles():
    sections = _sections(
        [
            _closed_section("SELF", "A", "A"),
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert results["topology_self_loops"]["SectionId"].tolist() == ["SELF"]


def test_phase_discontinuous_cycle_is_not_reported_as_energized_loop():
    sections = _sections(
        [
            _closed_section("S1", "A", "B", phases="A"),
            _closed_section("S2", "B", "C", phases="B"),
            _closed_section("S3", "C", "A", phases="C"),
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert results["loop_review_summary"].empty
    assert results["loop_sections"].empty
    assert results["physical_cycle_diagnostics"]["Reason"].tolist() == [
        "Physical ring is not phase-continuous"
    ]


def test_der_on_radial_feeder_does_not_create_loop_finding():
    sections = _sections(
        [
            _closed_section("S1", "A", "B", IsDER=True),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "D"),
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert results["loop_sections"].empty


def test_unknown_status_produces_review_only():
    sections = _sections(
        [
            {
                "SectionId": "S1",
                "FromNodeId": "A",
                "ToNodeId": "B",
                "FeederId": "F1",
                "SectionPhases": "ABC",
            },
            {
                "SectionId": "S2",
                "FromNodeId": "B",
                "ToNodeId": "C",
                "FeederId": "F1",
                "SectionPhases": "ABC",
            },
            {
                "SectionId": "S3",
                "FromNodeId": "C",
                "ToNodeId": "A",
                "FeederId": "F1",
                "SectionPhases": "ABC",
            },
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert len(results["loop_review_summary"]) == 1
    assert results["loop_review_summary"]["Severity"].tolist() == ["Review"]
    assert results["loop_review_summary"].iloc[0]["UnknownStatusCount"] == 3
    assert results["loop_section_details"].empty
    assert set(results["loop_review_section_details"]["SectionId"]) == {"S1", "S2", "S3"}
    assert results["loop_diagnostics"].set_index("Check").loc[
        f"Section state {UNKNOWN}", "Count"
    ] == 3


def test_approved_meshed_feeder_is_not_reported():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "A"),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "MESHED"})

    assert results["loop_summary"].empty
    assert results["loop_review_summary"].empty
    assert results["loop_section_details"].empty


def test_unknown_feeder_topology_closed_cycle_produces_review_only():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "A"),
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert len(results["loop_review_summary"]) == 1
    assert results["loop_review_summary"]["Severity"].tolist() == ["Review"]
    assert results["loop_section_details"].empty
    assert results["loop_review_section_details"]["Severity"].unique().tolist() == ["Review"]


def test_device_statuses_can_confirm_closed_sections_by_section_id():
    sections = _sections(
        [
            {"SectionId": "S1", "FromNodeId": "A", "ToNodeId": "B", "SectionPhases": "ABC"},
            {"SectionId": "S2", "FromNodeId": "B", "ToNodeId": "C", "SectionPhases": "ABC"},
        ]
    )
    devices = pd.DataFrame(
        [
            {"SectionId": "S1", "DeviceStatus": "CLOSED", "SwitchId": "SW1"},
            {"SectionId": "S2", "DeviceStatus": "CLOSED", "SwitchId": "SW2"},
        ]
    )

    closed_sections = filter_closed_sections(sections, device_statuses=devices)

    assert closed_sections["SectionState"].tolist() == [CLOSED, CLOSED]
    assert closed_sections["SwitchIdsForCheck"].tolist() == ["SW1", "SW2"]


def test_loop_section_rows_inherit_actual_loop_severity():
    sections = _sections(
        [
            _closed_section("S1", "A", "B", feeder="F1"),
            _closed_section("S2", "B", "C", feeder="F1"),
            _closed_section("TIE", "C", "A", feeder="F2"),
        ]
    )

    results = check_loops(sections)

    assert len(results["loop_summary"]) == 1
    assert results["loop_summary"]["Severity"].tolist() == ["Warning"]
    assert results["loop_section_details"]["Severity"].unique().tolist() == ["Warning"]
    assert results["loop_sections"]["Severity"].unique().tolist() == ["Warning"]


def test_ambiguous_status_strings_are_not_treated_as_closed_or_open():
    sections = _sections(
        [
            {
                "SectionId": "S1",
                "FromNodeId": "A",
                "ToNodeId": "B",
                "FeederId": "F1",
                "SectionPhases": "ABC",
                "Status": "NORMAL",
            },
            {
                "SectionId": "S2",
                "FromNodeId": "B",
                "ToNodeId": "C",
                "FeederId": "F1",
                "SectionPhases": "ABC",
                "Status": "NO",
            },
            {
                "SectionId": "S3",
                "FromNodeId": "C",
                "ToNodeId": "A",
                "FeederId": "F1",
                "SectionPhases": "ABC",
                "Status": "NORMAL",
            },
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert results["loop_review_summary"]["Severity"].tolist() == ["Review"]
    assert results["loop_review_summary"].iloc[0]["UnknownStatusCount"] == 3


def test_incomplete_endpoint_status_is_unknown_not_closed():
    sections = _sections(
        [
            {
                "SectionId": "S1",
                "FromNodeId": "A",
                "ToNodeId": "B",
                "FeederId": "F1",
                "SectionPhases": "ABC",
                "IsFromEndOpen": False,
            },
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "A"),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "RADIAL"})

    assert results["loop_summary"].empty
    assert results["loop_review_summary"]["Severity"].tolist() == ["Review"]
    assert results["loop_review_summary"].iloc[0]["UnknownStatusCount"] == 1


def test_partial_phase_data_closed_cycle_is_review_not_lost():
    sections = _sections(
        [
            _closed_section("S1", "A", "B", phases="ABC"),
            _closed_section("S2", "B", "C", phases="ABC"),
            _closed_section("S3", "C", "A", phases=""),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "RADIAL"})

    assert results["loop_summary"].empty
    assert results["loop_review_summary"]["Severity"].tolist() == ["Review"]
    assert "phase data is incomplete" in results["loop_review_summary"].iloc[0]["LikelyCause"]
    assert set(results["loop_review_section_details"]["SectionId"]) == {"S1", "S2", "S3"}


def test_hyphenated_node_ids_do_not_break_internal_signatures():
    sections = _sections(
        [
            _closed_section("S1", "N-1", "N-2"),
            _closed_section("S2", "N-2", "N-3"),
            _closed_section("TIE", "N-3", "N-1", SwitchId="SW-TIE"),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "RADIAL"})

    assert len(results["loop_summary"]) == 1
    assert results["loop_summary"]["Severity"].tolist() == ["Error"]
    assert results["loop_summary"].iloc[0]["SuspectSectionId"] == "TIE"


def test_unknown_cross_feeder_tie_produces_global_review():
    sections = _sections(
        [
            {
                "SectionId": "S1",
                "FromNodeId": "A",
                "ToNodeId": "B",
                "FeederId": "F1",
                "SectionPhases": "ABC",
            },
            {
                "SectionId": "S2",
                "FromNodeId": "B",
                "ToNodeId": "C",
                "FeederId": "F1",
                "SectionPhases": "ABC",
            },
            {
                "SectionId": "TIE",
                "FromNodeId": "C",
                "ToNodeId": "A",
                "FeederId": "F2",
                "SectionPhases": "ABC",
            },
        ]
    )

    results = check_loops(sections)

    assert results["loop_summary"].empty
    assert len(results["loop_review_summary"]) == 1
    assert results["loop_review_summary"].iloc[0]["FeederId"] == "CROSS_FEEDER"
    assert set(results["loop_review_section_details"]["SectionId"]) == {"S1", "S2", "TIE"}


def test_no_suspect_section_when_no_defensible_evidence_exists():
    sections = _sections(
        [
            _closed_section("S1", "A", "B"),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "A"),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "RADIAL"})

    assert results["loop_summary"].iloc[0]["SuspectSectionId"] is None
    assert not results["loop_section_details"]["IsSuspectSection"].any()
    assert results["loop_sections"].empty


def test_conflicting_device_statuses_do_not_confirm_closed():
    sections = _sections(
        [
            {
                "SectionId": "S1",
                "FromNodeId": "A",
                "ToNodeId": "B",
                "FeederId": "F1",
                "SectionPhases": "ABC",
            },
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "A"),
        ]
    )
    devices = pd.DataFrame(
        [
            {"SectionId": "S1", "DeviceStatus": "CLOSED"},
            {"SectionId": "S1", "DeviceStatus": "OPEN"},
        ]
    )

    results = check_loops(sections, device_statuses=devices, feeder_topology={"F1": "RADIAL"})

    assert results["loop_summary"].empty
    assert results["physical_cycle_diagnostics"].iloc[0]["OpenSectionCount"] == 1


def test_overlapping_cycle_basis_reports_independent_cycles_not_all_simple_cycles():
    sections = _sections(
        [
            _closed_section("S1", "A", "B", SwitchId="SW1"),
            _closed_section("S2", "B", "C"),
            _closed_section("S3", "C", "D"),
            _closed_section("S4", "D", "A"),
            _closed_section("S5", "A", "C"),
        ]
    )

    results = check_loops(sections, feeder_topology={"F1": "RADIAL"})

    assert len(results["loop_summary"]) == 2
    assert set(results["loop_summary"]["Severity"]) == {"Error"}
