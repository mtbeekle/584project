# topology/unfed_sections.py

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import add_rule_columns, validate_required_columns
from topology.graph_builder import build_section_graph


def check_unfed_sections(sections: pd.DataFrame) -> dict:
    """
    VR1 - Unfed / disconnected sections

    First-pass source-free implementation.

    Since the MDB does not provide explicit source_node_ids, this check uses
    connected components as an a priori topology validation method.

    The largest connected component is treated as the main feeder/model
    component. Sections outside that component are flagged as disconnected
    topology sections.

    Limitation:
    This does not prove electrical energization from a true source. It flags
    sections disconnected from the main topology component.
    """
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    graph = build_section_graph(sections)

    if graph.number_of_nodes() == 0:
        unfed_sections = add_rule_columns(
            sections.copy(),
            rule=get_rule("VR1"),
            element_type="Section",
            element_id="SectionId",
        )
        return {"unfed_sections": unfed_sections}

    components = list(nx.connected_components(graph))

    if not components:
        unfed_sections = add_rule_columns(
            sections.copy(),
            rule=get_rule("VR1"),
            element_type="Section",
            element_id="SectionId",
        )
        return {"unfed_sections": unfed_sections}

    main_component = max(components, key=len)

    unfed_mask = (
        sections["FromNodeId"].notna()
        & sections["ToNodeId"].notna()
        & ~sections["FromNodeId"].isin(main_component)
        & ~sections["ToNodeId"].isin(main_component)
    )

    unfed_sections = add_rule_columns(
        sections[unfed_mask].copy(),
        rule=get_rule("VR1"),
        element_type="Section",
        element_id="SectionId",
    )

    if not unfed_sections.empty:
        unfed_sections["Issue"] = "Disconnected topology section"
        unfed_sections["Description"] = (
            "Section is outside the largest connected topology component. "
            "This indicates a possible unfed or disconnected island."
        )
        unfed_sections["RecommendedAction"] = (
            "Review section connectivity, upstream path, open devices, and whether "
            "this disconnected island is intentional."
        )

    return {"unfed_sections": unfed_sections}
