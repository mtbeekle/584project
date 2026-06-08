# topology/loops.py

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import add_rule_columns, validate_required_columns


def build_active_section_graph(sections: pd.DataFrame) -> nx.Graph:
    """
    Build an undirected graph from section FromNodeId / ToNodeId connectivity.

    Each edge represents one Synergi section.
    Multiple sections between the same two nodes are preserved by storing
    section IDs as edge attributes where possible.

    This version assumes all sections passed in are active. Later, this can be
    refined to exclude normally-open switches, open fuses, inactive sections,
    or other de-energized equipment.
    """

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    graph = nx.Graph()

    valid_sections = sections.dropna(
        subset=["SectionId", "FromNodeId", "ToNodeId"]
    )

    for _, row in valid_sections.iterrows():
        from_node = row["FromNodeId"]
        to_node = row["ToNodeId"]
        section_id = row["SectionId"]

        graph.add_edge(
            from_node,
            to_node,
            SectionId=section_id,
        )

    return graph


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
    VR2 - Loops

    Identify sections that appear to be part of a loop in a network expected
    to be radial.

    Current limitation:
    This first-pass version uses all section connectivity as active. It does
    not yet account for normally-open switches, open protective devices, or
    sponsor-approved looped configurations.
    """

    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    graph = build_active_section_graph(sections)

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

    return {
        "loop_sections": loop_sections,
    }
