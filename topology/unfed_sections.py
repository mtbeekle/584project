# topology/unfed_sections.py

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import add_rule_columns, validate_required_columns
from topology.graph_builder import build_section_graph


def check_unfed_sections(sections: pd.DataFrame, source_node_ids: set) -> dict:
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    graph = build_section_graph(sections)

    reachable_nodes = set()

    for source_node in source_node_ids:
        if source_node in graph:
            reachable_nodes.update(nx.node_connected_component(graph, source_node))

    unfed_mask = (
        ~sections["FromNodeId"].isin(reachable_nodes)
        & ~sections["ToNodeId"].isin(reachable_nodes)
    )

    unfed_sections = add_rule_columns(
        sections[unfed_mask],
        rule=get_rule("VR1"),
        element_type="Section",
        element_id="SectionId",
    )

    return {"unfed_sections": unfed_sections}
