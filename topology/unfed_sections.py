# topology/unfed_sections.py

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import add_rule_columns, validate_required_columns
from topology.graph_builder import build_section_graph


def _format_sample(values: pd.Series) -> str:
    return ", ".join(values.dropna().astype(str).head(10).tolist())


def build_component_summary(sections: pd.DataFrame) -> pd.DataFrame:
    """
    Build diagnostic metadata describing section connectivity components.

    This is not a validation issue table. It helps explain disconnected
    topology counts by showing how many separate components exist in the
    section graph and which sections/nodes are represented in each component.
    """
    graph = build_section_graph(sections)

    rows = []
    components = list(nx.connected_components(graph))
    largest_component = max(components, key=len) if components else set()

    for component in components:
        section_mask = (
            sections["FromNodeId"].isin(component)
            & sections["ToNodeId"].isin(component)
        )
        component_sections = sections[section_mask]

        rows.append(
            {
                "NodeCount": len(component),
                "SectionCount": len(component_sections),
                "IsLargestComponent": component == largest_component,
                "SampleNodeIds": ", ".join(
                    str(node)
                    for node in sorted(component, key=lambda value: str(value))[:10]
                ),
                "SampleSectionIds": _format_sample(
                    component_sections["SectionId"]
                ),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "ComponentID",
                "NodeCount",
                "SectionCount",
                "IsLargestComponent",
                "SampleNodeIds",
                "SampleSectionIds",
            ]
        )

    summary = pd.DataFrame(rows).sort_values(
        by="SectionCount",
        ascending=False,
    )
    summary.insert(0, "ComponentID", range(1, len(summary) + 1))

    return summary.reset_index(drop=True)


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

    Diagnostic note:
    DisconnectedTopology is currently a source-free, component-based
    approximation. High disconnected counts may indicate multiple
    feeders/circuits in one MDB, not necessarily real unfed sections. A future
    improvement should group topology checks by feeder/circuit if the correct
    grouping column is identified.
    """
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    topology_components = build_component_summary(sections)
    graph = build_section_graph(sections)

    if graph.number_of_nodes() == 0:
        unfed_sections = add_rule_columns(
            sections.copy(),
            rule=get_rule("VR1"),
            element_type="Section",
            element_id="SectionId",
        )
        return {
            "unfed_sections": unfed_sections,
            "topology_components": topology_components,
        }

    components = list(nx.connected_components(graph))

    if not components:
        unfed_sections = add_rule_columns(
            sections.copy(),
            rule=get_rule("VR1"),
            element_type="Section",
            element_id="SectionId",
        )
        return {
            "unfed_sections": unfed_sections,
            "topology_components": topology_components,
        }

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

    return {
        "unfed_sections": unfed_sections,
        "topology_components": topology_components,
    }
