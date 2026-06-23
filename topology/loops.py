# topology/loops.py

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    normalize_boolean_value,
    validate_required_columns,
)
from topology.graph_builder import build_section_graph


LOOP_REVIEW_ISSUE = "Potential loop or meshed topology"
LOOP_REVIEW_DESCRIPTION = (
    "Section appears to be part of a graph cycle. This may indicate a topology "
    "issue, a normally-open tie, a valid meshed area, or a DER/source-related "
    "configuration."
)
LOOP_REVIEW_RECOMMENDED_ACTION = (
    "Review switching status, tie devices, source/DER locations, and whether "
    "this loop is intentional."
)
OPEN_END_COLUMNS = ["IsFromEndOpen", "IsToEndOpen"]


def _true_mask(values: pd.Series) -> pd.Series:
    return values.map(normalize_boolean_value).eq(True)


def filter_closed_sections(sections: pd.DataFrame) -> pd.DataFrame:
    """
    Return sections whose section endpoints are not marked open.

    InstSection end-open fields are available in the MDB and capture normally
    open/open switching state for topology connectivity. Graph cycle detection
    should not treat those open endpoints as closed electrical paths.
    """
    open_mask = pd.Series(False, index=sections.index)

    for column in OPEN_END_COLUMNS:
        if column in sections.columns:
            open_mask |= _true_mask(sections[column])

    return sections[~open_mask].copy()


def find_loop_section_ids(
    graph: nx.Graph,
) -> set:
    """
    Find section IDs that are part of graph cycles.

    Returns a set of SectionId values associated with edges that participate
    in at least one detected cycle.
    """

    loop_section_ids = set()

    cycles = nx.cycle_basis(graph)

    for cycle in cycles:
        # cycle is a list of nodes, for example:
        # [node_a, node_b, node_c]
        #
        # Need to check edges:
        # node_a-node_b, node_b-node_c, node_c-node_a

        cycle_edges = list(zip(cycle, cycle[1:] + cycle[:1]))

        for from_node, to_node in cycle_edges:
            edge_data = graph.get_edge_data(from_node, to_node)

            if edge_data is None:
                continue

            section_id = edge_data.get("SectionId")

            if pd.notna(section_id):
                loop_section_ids.add(section_id)

    return loop_section_ids


def check_loops(sections: pd.DataFrame) -> dict:
    """
    VR2 - Potential loop or meshed topology review

    Source-free topology diagnostic that identifies closed sections that appear
    to be part of a graph cycle.

    Limitation:
    This does not prove an invalid electrical loop. It uses InstSection open-end
    status when available, but does not yet account for multiple valid sources,
    rooftop solar, DER, detailed device state outside InstSection, or feeder
    grouping. Future improvement should identify actual source/feeder/DER
    devices and active switching status from MDB tables.
    """

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    closed_sections = filter_closed_sections(sections)
    graph = build_section_graph(closed_sections)

    loop_section_ids = find_loop_section_ids(graph)

    loop_sections = sections[
        sections["SectionId"].isin(loop_section_ids)
    ].copy()

    loop_sections = add_rule_columns(
        loop_sections,
        rule=get_rule("VR2"),
        element_type="Section",
        element_id="SectionId",
    )
    loop_sections["Severity"] = "Review"
    loop_sections["Issue"] = LOOP_REVIEW_ISSUE
    loop_sections["Description"] = LOOP_REVIEW_DESCRIPTION
    loop_sections["RecommendedAction"] = LOOP_REVIEW_RECOMMENDED_ACTION

    return {
        "loop_sections": loop_sections,
    }
