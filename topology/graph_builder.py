# topology/graph_builder.py

import pandas as pd
import networkx as nx

from validation_utils import validate_required_columns


def build_section_graph(sections: pd.DataFrame) -> nx.Graph:
    """
    Build an undirected graph from section FromNodeId / ToNodeId connectivity.

    Each edge represents one Synergi section.

    Current limitation:
    This first-pass version assumes all sections are active. Later this should be
    refined to exclude normally-open switches, open fuses, inactive sections,
    or other de-energized equipment once the correct MDB status fields are
    confirmed.
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
        graph.add_edge(
            row["FromNodeId"],
            row["ToNodeId"],
            SectionId=row["SectionId"],
        )

    return graph
