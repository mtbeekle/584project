# topology/unfed_sections.py

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    normalize_boolean_value,
    validate_required_columns,
)
from topology.graph_builder import build_section_graph


ISOLATED_COMPONENT_ISSUE = "Isolated topology component"
ISOLATED_COMPONENT_DESCRIPTION = (
    "Section is outside the largest connected topology component. This may "
    "indicate an unfed section, separate feeder/source area, DER island, or "
    "disconnected model island."
)
ISOLATED_COMPONENT_RECOMMENDED_ACTION = (
    "Review feeder/source assignment, switching status, DER/source devices, "
    "and whether this component is intentionally separate."
)


def _format_sample(values: pd.Series) -> str:
    return ", ".join(values.dropna().astype(str).head(10).tolist())


def _false_mask(values: pd.Series) -> pd.Series:
    return values.map(normalize_boolean_value).eq(False)


def _apply_isolated_component_metadata(sections: pd.DataFrame) -> pd.DataFrame:
    sections["Severity"] = "Review"
    sections["Issue"] = ISOLATED_COMPONENT_ISSUE
    sections["Description"] = ISOLATED_COMPONENT_DESCRIPTION
    sections["RecommendedAction"] = ISOLATED_COMPONENT_RECOMMENDED_ACTION
    return sections


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
    total_sections = len(sections)

    for component in components:
        section_mask = (
            sections["FromNodeId"].isin(component)
            & sections["ToNodeId"].isin(component)
        )
        component_sections = sections[section_mask]
        section_count = len(component_sections)

        rows.append(
            {
                "NodeCount": len(component),
                "SectionCount": section_count,
                "IsLargestComponent": component == largest_component,
                "PercentOfTotalSections": (
                    round(section_count / total_sections * 100, 2)
                    if total_sections
                    else 0
                ),
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
                "PercentOfTotalSections",
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


def _find_sections_outside_largest_component(sections: pd.DataFrame) -> pd.Series:
    graph = build_section_graph(sections)

    if graph.number_of_nodes() == 0:
        return pd.Series(True, index=sections.index)

    components = list(nx.connected_components(graph))

    if not components:
        return pd.Series(True, index=sections.index)

    main_component = max(components, key=len)

    return (
        sections["FromNodeId"].notna()
        & sections["ToNodeId"].notna()
        & ~sections["FromNodeId"].isin(main_component)
        & ~sections["ToNodeId"].isin(main_component)
    )


def _find_isolated_component_sections(sections: pd.DataFrame) -> pd.Series:
    if "IsFed" in sections.columns:
        # Synergi's IsFed field already reflects the model's known source and
        # switching state. Prefer it over source-free graph inference when it is
        # available so valid feeder/source areas are not flagged as unfed.
        return _false_mask(sections["IsFed"])

    if "FeederId" not in sections.columns:
        return _find_sections_outside_largest_component(sections)

    isolated_mask = pd.Series(False, index=sections.index)

    # Fallback for MDBs without IsFed: compare components inside each feeder,
    # not across the whole MDB. A distribution model can contain multiple valid
    # feeder/source areas, so a single global largest component is not a valid
    # source proxy.
    for _, feeder_sections in sections.groupby("FeederId", dropna=False):
        isolated_mask.loc[feeder_sections.index] = (
            _find_sections_outside_largest_component(feeder_sections)
        )

    return isolated_mask


def check_unfed_sections(sections: pd.DataFrame) -> dict:
    """
    VR1 - Isolated topology component review

    Topology diagnostic.

    When InstSection.IsFed is available, this check uses that MDB field because
    it reflects the model's known source and switching state. If IsFed is not
    available, it falls back to a source-free connected-component diagnostic
    grouped by FeederId when possible.

    The largest connected component is used only as a fallback reference
    component for review. Sections outside that fallback component are reported
    as isolated topology components, not confirmed unfed sections.

    Limitation:
    This does not prove electrical energization. It does not yet account for
    multiple valid sources, rooftop solar, DER, normally-open switches, or
    feeder grouping. Future improvement should identify actual
    source/feeder/DER devices and active switching status from MDB tables.
    """
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    topology_components = build_component_summary(sections)
    unfed_mask = _find_isolated_component_sections(sections)

    unfed_sections = add_rule_columns(
        sections[unfed_mask].copy(),
        rule=get_rule("VR1"),
        element_type="Section",
        element_id="SectionId",
    )
    unfed_sections = _apply_isolated_component_metadata(unfed_sections)

    return {
        "unfed_sections": unfed_sections,
        "topology_components": topology_components,
    }
