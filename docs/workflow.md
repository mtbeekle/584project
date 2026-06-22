# Workflow

## Recommended Project Workflow
1. Put the original Synergi `.mdb` file in `data/raw/`.
2. Run `inspect_mdb.py` with `--columns` to identify available tables and fields.
3. Export important tables to CSV when needed.
4. Identify tables that represent feeder nodes, lines, switches, transformers, loads, sources, capacitors, regulators, and connectivity.
5. Build validation checks one at a time.
6. Save validation output in `data/exports/`.

## Running the Validation Tool
Run the full validation workflow from the repository root:

```powershell
python main.py
```

The report is written to `data/exports/synergi_validation_results.xlsx` unless a different path is supplied with `--output-file`.

The report includes a summary sheet, a consolidated `Issues` sheet, and one sheet per check result. Current check sheets include missing data checks, capacitor issues, fuse and unfed section checks, conductor height, connected load, customer count, conductor mismatch, and incorrect phase results.

## Check Module Pattern
Validation check modules live in `checks/`. New checks should:

1. Validate required input columns with `validate_required_columns`.
2. Use `get_rule(...)` from `rules.py` for rule metadata.
3. Add standard output columns with `add_rule_columns`.
4. Return a dictionary of named `pandas.DataFrame` results so `reports/report_writer.py` can include them in the Excel output.

## Input and Output Folders
Recommended structure:

```text
data/raw/      Original Synergi .mdb files
data/exports/  CSV files exported from .mdb tables
```
