# topology/graph_builder.py

import pandas as pd
import networkx as nx

from validation_utils import validate_required_columns


REQUIRED_SECTION_COLUMNS = ["SectionId", "FromNodeId", "ToNodeId"]


def _is_blank(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _normalized_node_id(value) -> str:
    return str(value).strip()


def valid_section_mask(sections: pd.DataFrame) -> pd.Series:
    """
    Return sections that can be represented as graph edges.

    Self-loops are excluded from the graph and reported separately by the VR2
    topology diagnostics.
    """
    validate_required_columns(sections, "sections", REQUIRED_SECTION_COLUMNS)

    has_required_values = pd.Series(True, index=sections.index)
    for column in REQUIRED_SECTION_COLUMNS:
        has_required_values &= ~sections[column].map(_is_blank).astype(bool)

    from_nodes = sections["FromNodeId"].map(_normalized_node_id)
    to_nodes = sections["ToNodeId"].map(_normalized_node_id)

    return has_required_values & from_nodes.ne(to_nodes)


def find_self_loop_sections(sections: pd.DataFrame) -> pd.DataFrame:
    """Return section rows where FromNodeId and ToNodeId identify the same node."""
    validate_required_columns(sections, "sections", REQUIRED_SECTION_COLUMNS)

    has_nodes = ~sections["FromNodeId"].map(_is_blank) & ~sections["ToNodeId"].map(_is_blank)
    same_node = (
        sections["FromNodeId"].map(_normalized_node_id)
        == sections["ToNodeId"].map(_normalized_node_id)
    )

    return sections[has_nodes & same_node].copy()


def find_duplicate_section_ids(sections: pd.DataFrame) -> pd.DataFrame:
    """Return section rows with nonblank SectionId values used more than once."""
    validate_required_columns(sections, "sections", ["SectionId"])

    nonblank = ~sections["SectionId"].map(_is_blank)
    duplicate_mask = sections.loc[nonblank, "SectionId"].duplicated(keep=False)
    result = sections.loc[nonblank].loc[duplicate_mask].copy()

    if not result.empty:
        duplicate_counts = result.groupby("SectionId")["SectionId"].transform("size")
        result["DuplicateSectionIdCount"] = duplicate_counts

    return result


def unordered_endpoint_pair(from_node, to_node) -> tuple[str, str]:
    """Return a stable unordered endpoint-pair key for an undirected section."""
    endpoints = sorted([_normalized_node_id(from_node), _normalized_node_id(to_node)])
    return endpoints[0], endpoints[1]


def find_parallel_endpoint_sections(sections: pd.DataFrame) -> pd.DataFrame:
    """
    Return valid section rows whose unordered endpoint pair appears more than once.

    This is separate from duplicate SectionId detection. Parallel physical
    sections are preserved as separate MultiGraph edges but are reported as
    diagnostic evidence because they can otherwise look like graph cycles.
    """
    validate_required_columns(sections, "sections", REQUIRED_SECTION_COLUMNS)

    valid_sections = sections[valid_section_mask(sections)].copy()
    if valid_sections.empty:
        return valid_sections

    endpoint_pairs = valid_sections.apply(
        lambda row: unordered_endpoint_pair(row["FromNodeId"], row["ToNodeId"]),
        axis=1,
    )
    valid_sections["EndpointPair"] = endpoint_pairs.map(lambda pair: f"{pair[0]}|{pair[1]}")
    valid_sections["ParallelEndpointSectionCount"] = (
        valid_sections.groupby("EndpointPair")["SectionId"].transform("size")
    )

    return valid_sections[valid_sections["ParallelEndpointSectionCount"] > 1].copy()


def build_section_graph(sections: pd.DataFrame) -> nx.MultiGraph:
    """
    Build an undirected MultiGraph from section FromNodeId / ToNodeId connectivity.

    Each valid section row is preserved as a separate edge. The edge key is the
    dataframe index so duplicate SectionId values and parallel sections cannot
    overwrite each other.
    """
    validate_required_columns(sections, "sections", REQUIRED_SECTION_COLUMNS)

    graph = nx.MultiGraph()
    valid_sections = sections[valid_section_mask(sections)]

    for index, row in valid_sections.iterrows():
        edge_attributes = row.to_dict()
        edge_attributes["RowIndex"] = index
        graph.add_edge(
            row["FromNodeId"],
            row["ToNodeId"],
            key=index,
            **edge_attributes,
        )

    return graph
