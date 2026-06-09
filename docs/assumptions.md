# Project Assumptions

This document records the main assumptions used during development of the Synergi MDB validation tool. These assumptions should be reviewed and updated as additional sponsor guidance, sample data, or Synergi model conventions become available.

## 1. Project Boundary Assumptions

1. This project is a validation tool, not a data correction tool.
   - The software is intended to identify and report potential inconsistencies.
   - The software does not automatically modify, repair, or overwrite Synergi MDB data.

2. The tool operates after GIS-to-MDB conversion.
   - The tool validates the MDB output produced by the existing conversion process.
   - The tool does not redesign or replace the GIS-to-MDB conversion workflow.

3. The tool supports pre-analysis model quality review.
   - The tool is intended to help engineers review converted model data before Synergi analysis.
   - The tool does not run or replace Synergi power flow, protection, or planning studies.

## 2. Data Access Assumptions

1. At least one representative Synergi MDB or ACCDB file will be available for development and testing.

2. MDB data can be accessed from Python using `pyodbc`, `pandas`, or equivalent tools.

3. Required Synergi tables and fields may vary between datasets.
   - The code should validate required columns before running each rule.
   - Missing required fields should produce clear errors instead of silent failures.

4. The MDB schema used during development is treated as a working baseline, not a universal Synergi schema.

5. Sensitive or confidential sponsor data should not be committed to the repository.
   - Sample MDB files should remain local unless explicitly approved for sharing.
   - Exported reports containing sponsor data should be handled carefully.

## 3. Rule Definition Assumptions

1. The sponsor-provided validation rule list is the starting scope for development.

2. Rule behavior may need refinement after sponsor review.
   - Some issue definitions may require tolerance values, exceptions, or sponsor-specific interpretation.
   - Rules that produce false positives should be documented and adjusted as needed.

3. Each validation check should be implemented as an independent function or module when practical.

4. Rule metadata should be standardized across the report.
   - Expected metadata includes rule ID, category, severity, element type, element ID, issue, description, and recommended action.

5. Rules may be added, removed, or modified as the project evolves, but major scope changes should be documented.

## 4. Reporting Assumptions

1. The primary output is a structured Excel report.

2. The report should be understandable to engineering reviewers with minimal Python knowledge.

3. The report should include a combined Issues tab plus supporting tabs where useful.

4. The Issues tab should prioritize readability.
   - Important columns should appear first.
   - Severity, issue description, and recommended action should be easy to identify.
   - Formatting may be applied using `openpyxl` to improve review quality.

5. Report output is intended to support engineering review, not to serve as a final automated pass/fail certification.

## 5. Topology Assumptions

1. Topology validation is expected to be more complex than simple field-level validation.

2. Section connectivity is assumed to be represented using section IDs and from-node/to-node relationships.

3. Preliminary topology checks may treat all sections as active unless reliable switch, fuse, or device status fields are incorporated.

4. Loop detection should be treated as preliminary until normally-open switches, open protective devices, and acceptable looped configurations are accounted for.

5. Unfed-section detection requires a reliable method for identifying source nodes or source-connected sections.

6. Graph-based topology checks may require sponsor review to confirm whether flagged conditions are true model errors or acceptable configurations.

## 6. Device and Component Assumptions

1. Fuse status fields can be interpreted as open or closed using known true/false value mappings.

2. Capacitor checks assume capacitor phase, rating, and connected section fields are available and consistently populated.

3. Regulator and transformer-regulator checks may require additional sponsor clarification because expected positioning and device relationships may depend on Synergi modeling conventions.

4. Source voltage checks require a defined expected voltage reference.
   - This may come from feeder metadata, source metadata, section ratings, or sponsor-provided expected values.

## 7. Circuit Data Assumptions

1. Connected load checks assume load records can be associated with sections using a common section identifier.

2. Load values may be represented by total kVA fields or by per-phase kVA, kW, or kVAR fields depending on the dataset.

3. Conductor height checks assume conductor type can be inferred from conductor ID or descriptive text when explicit overhead/underground classification is unavailable.

4. Negative or positive height values may require sponsor confirmation.
   - A preliminary assumption may be that overhead conductors should have positive height values and underground conductors should have negative height values.

5. Phase comparison checks assume phase labels can be normalized into comparable phase sets.

## 8. Testing Assumptions

1. Rule testing should use both representative MDB data and small controlled test cases where possible.

2. The test dataset may not contain every issue type.
   - Some rules may need synthetic test cases to confirm behavior.

3. False positives and false negatives should be documented during review.

4. Runtime performance requirements will be refined after realistic dataset size is known.

## 9. Documentation Assumptions

1. The repository should include enough documentation for another user to install dependencies, provide an MDB file, run the tool, and interpret the report.

2. Rule documentation should describe each check’s purpose, required fields, logic summary, severity, and known limitations.

3. A data dictionary should be maintained as required MDB tables and fields are confirmed.

4. Assumptions should be updated as the project matures and sponsor feedback is received.