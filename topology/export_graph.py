import argparse
from pathlib import Path
import sys

import networkx as nx

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from mdb_utils import connect_to_mdb, find_default_mdb_file, read_table
from topology.graph_builder import build_section_graph

EXPORTS_DIR = PROJECT_DIR / "data" / "exports"
DEFAULT_OUTPUT_FILE = EXPORTS_DIR / "section_graph.graphml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the Synergi section connectivity graph to GraphML."
    )
    parser.add_argument(
        "mdb_path",
        nargs="?",
        help="Path to the .mdb/.accdb file. Default: the only .mdb/.accdb file in data/raw.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Output GraphML file. Default: data/exports/section_graph.graphml",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mdb_file = Path(args.mdb_path).expanduser() if args.mdb_path else find_default_mdb_file()
    output_file = args.output_file

    if not mdb_file.is_absolute():
        mdb_file = PROJECT_DIR / mdb_file

    if not output_file.is_absolute():
        output_file = PROJECT_DIR / output_file

    if not mdb_file.exists():
        raise FileNotFoundError(mdb_file)

    print(f"MDB file found: {mdb_file}")

    with connect_to_mdb(mdb_file) as connection:
        print("Connected successfully!")
        sections = read_table(connection, "InstSection")
        graph = build_section_graph(sections)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, output_file)

    print(f"Graph nodes: {graph.number_of_nodes()}")
    print(f"Graph edges: {graph.number_of_edges()}")
    print(f"Graph exported to:\n{output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
