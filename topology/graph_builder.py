# topology/graph_builder.py

import pandas as pd
import networkx as nx

from validation_utils import validate_required_columns


def build_section_graph(sections: pd.DataFrame) -> nx.Graph:
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "FromNodeId", "ToNodeId"],
    )

    graph = nx.Graph()

    valid_sections = sections.dropna(subset=["FromNodeId", "ToNodeId"])

    for _, row in valid_sections.iterrows():
        graph.add_edge(
            row["FromNodeId"],
            row["ToNodeId"],
            SectionId=row["SectionId"],
        )

    return graph