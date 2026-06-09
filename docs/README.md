# Documentation

This folder contains project documentation for the Synergi MDB validation tool. These files are intended to help users install the tool, inspect MDB data, understand the validation workflow, and review the assumptions and rule definitions used by the project.

## Documentation Index

- [Setup](./setup.md) - Platform requirements, Python dependencies, ODBC driver requirements, and environment verification steps.
- [Inspect MDB](./inspect-mdb.md) - Commands for inspecting MDB tables, listing columns, previewing records, and exporting tables to CSV.
- [Workflow](./workflow.md) - Recommended workflow for placing MDB files, inspecting schemas, building checks, and saving validation outputs.
- [Validation Notes](./validation-notes.md) - Early validation ideas and schema notes for Synergi MDB data.
- [Project Assumptions](./assumptions.md) - Project boundary, data access, reporting, topology, device, circuit data, testing, and documentation assumptions.
- [Rule Definitions](./rule_definitions.md) - Validation rule metadata and implementation notes matching the `RULES` registry in `rules.py`.

## Suggested Reading Order

1. Start with [Setup](./setup.md) to confirm the required Python environment and Access ODBC driver.
2. Use [Inspect MDB](./inspect-mdb.md) to examine the available tables and fields in a Synergi MDB file.
3. Review [Workflow](./workflow.md) to understand the expected development and validation process.
4. Read [Project Assumptions](./assumptions.md) before interpreting validation results or changing rule logic.
5. Use [Rule Definitions](./rule_definitions.md) as the reference for rule IDs, severity levels, descriptions, and recommended actions.

## Maintenance Notes

- Update [Rule Definitions](./rule_definitions.md) whenever `rules.py` changes.
- Update [Project Assumptions](./assumptions.md) whenever sponsor guidance, Synergi schema knowledge, or validation limitations change.
- Keep setup and workflow instructions aligned with the current repository structure and command-line scripts.