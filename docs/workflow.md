# Workflow

## Recommended Project Workflow
1. Put the original Synergi `.mdb` file in `data/raw/`.
2. Run `inspect_mdb.py` with `--columns` to identify available tables and fields.
3. Export important tables to CSV when needed.
4. Identify tables that represent feeder nodes, lines, switches, transformers, loads, sources, capacitors, regulators, and connectivity.
5. Build validation checks one at a time.
6. Save validation output in `data/exports/`.

## Input and Output Folders
Recommended structure:

```text
data/raw/      Original Synergi .mdb files
data/exports/  CSV files exported from .mdb tables
```
