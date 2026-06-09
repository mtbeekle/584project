# Rule Definitions

This document describes the validation rules implemented or planned for the Synergi MDB validation tool. The rule metadata in this document is intended to match the project rule registry in `rules.py`.

Each rule includes the rule ID, category, severity, issue name, description, and recommended action used in the validation report.

## Rule Summary Table

| Rule ID | Category | Severity | Issue |
|---|---|---|---|
| VR1 | Topology | Error | Unfed section |
| VR2 | Topology | Error | Potential loop detected |
| VR3 | Component / Device | Error | Source voltage mismatch |
| VR4 | Component / Device | Warning | Open fuse |
| VR5 | Component / Device | Warning | Capacitor zero or missing rating |
| VR6 | Component / Device | Error | Capacitor voltage mismatch |
| VR7 | Component / Device | Error | Capacitor phase mismatch |
| VR8 | Component / Device | Error | Regulator phase or section mismatch |
| VR9 | Component / Device | Review | XFMR-regulator pair positioning issue |
| VR10 | Circuit Data | Warning | No connected kVA |
| VR11 | Circuit Data | Warning | Section at negative height |
| VR12 | Circuit Data | Warning | Different conductors on one section |
| VR13 | Circuit Data | Error | Fewer upstream phases |
| VR14 | Circuit Data | Warning | Customer count missing |

## VR1 - Unfed Section

**Category:** Topology

**Severity:** Error

**Issue:** Unfed section

**Description:** Section is unfed or disconnected from a valid source.

**Recommended Action:** Review upstream connectivity, source path, switching status, and source assignment.

**Implementation Notes:**

This rule is intended to identify sections that are not electrically connected to a valid source. A complete implementation should use graph-based reachability from known source nodes or source-connected sections.

Preliminary implementations may rely on available MDB fields such as `IsFed`, but that should be documented as a limitation until full graph traversal is implemented.

## VR2 - Potential Loop Detected

**Category:** Topology

**Severity:** Error

**Issue:** Potential loop detected

**Description:** Potential loop detected in feeder topology.

**Recommended Action:** Review feeder connectivity and confirm whether the loop is intentional or should be corrected.

**Implementation Notes:**

This rule is intended to identify loops in a network expected to be radial. A complete implementation should account for normally-open switches, open protective devices, and sponsor-approved looped configurations.

If the current implementation assumes all sections are active, results should be treated as potential loops requiring engineering review.

## VR3 - Source Voltage Mismatch

**Category:** Component / Device

**Severity:** Error

**Issue:** Source voltage mismatch

**Description:** Source voltage does not match expected feeder voltage.

**Recommended Action:** Compare source nominal voltage against feeder, system, or connected section voltage values.

**Implementation Notes:**

This rule requires a reliable expected voltage reference. The expected voltage may come from feeder metadata, source metadata, section ratings, connected device ratings, or sponsor-provided values.

Voltage tolerance should be confirmed with the sponsor before finalizing the rule.

## VR4 - Open Fuse

**Category:** Component / Device

**Severity:** Warning

**Issue:** Open fuse

**Description:** Fuse is open in converted model; review device status.

**Recommended Action:** Confirm whether the fuse should be open in the normal converted model.

**Implementation Notes:**

This rule checks fuse status fields for values that indicate an open state. The rule depends on consistent interpretation of true/false or open/closed values in the MDB data.

Open fuses may be valid in some operating configurations, so this rule is classified as a warning.

## VR5 - Capacitor Zero or Missing Rating

**Category:** Component / Device

**Severity:** Warning

**Issue:** Capacitor zero or missing rating

**Description:** Capacitor has zero or missing rating.

**Recommended Action:** Review capacitor kVAR fields and populate a valid rating if needed.

**Implementation Notes:**

This rule identifies capacitor records with no configured reactive power rating. The implementation may check fixed kVAR fields, switched module kVAR fields, or other capacitor rating fields depending on available MDB columns.

## VR6 - Capacitor Voltage Mismatch

**Category:** Component / Device

**Severity:** Error

**Issue:** Capacitor voltage mismatch

**Description:** Capacitor voltage mismatches connected circuit voltage.

**Recommended Action:** Compare capacitor nominal voltage against the connected section or bus voltage.

**Implementation Notes:**

This rule requires capacitor voltage fields and a reliable connected circuit voltage reference. The voltage comparison method and acceptable tolerance should be confirmed with the sponsor.

## VR7 - Capacitor Phase Mismatch

**Category:** Component / Device

**Severity:** Error

**Issue:** Capacitor phase mismatch

**Description:** Capacitor phases do not match connected section phases.

**Recommended Action:** Review capacitor connected phases and section phase designation.

**Implementation Notes:**

This rule compares the capacitor phase designation against the phase designation of the connected section. Phase values should be normalized before comparison so values such as `ABC`, `A B C`, or other Synergi-specific formats can be compared consistently.

## VR8 - Regulator Phase or Section Mismatch

**Category:** Component / Device

**Severity:** Error

**Issue:** Regulator phase or section mismatch

**Description:** Regulator phases or sections are mismatched.

**Recommended Action:** Review regulator phase count, associated section IDs, and connected section phase designations.

**Implementation Notes:**

This rule checks whether regulator phase attributes and section associations are consistent with connected model elements. The final implementation may require sponsor clarification on Synergi regulator modeling conventions.

## VR9 - XFMR-Regulator Pair Positioning Issue

**Category:** Component / Device

**Severity:** Review

**Issue:** XFMR-regulator pair positioning issue

**Description:** XFMR-regulator pair positioning appears inconsistent.

**Recommended Action:** Review transformer/regulator adjacency and expected ordering in the converted topology.

**Implementation Notes:**

This rule evaluates whether transformer and regulator devices are positioned or paired as expected in the converted model topology. Because acceptable configurations may vary, this rule is classified as `Review` rather than `Error`.

Sponsor guidance is needed to define the exact expected arrangement.

## VR10 - No Connected kVA

**Category:** Circuit Data

**Severity:** Warning

**Issue:** No connected kVA

**Description:** Feeder or section has no connected kVA.

**Recommended Action:** Confirm whether load is expected and review connected customer or load records.

**Implementation Notes:**

This rule identifies feeders or sections with load records but no connected load value. The implementation may use total kVA fields or summed per-phase kVA, kW, or kVAR fields depending on the available MDB schema.

Some feeders or sections may intentionally have no connected load, so this rule is classified as a warning.

## VR11 - Section at Negative Height

**Category:** Circuit Data

**Severity:** Warning

**Issue:** Section at negative height

**Description:** Section has negative height or elevation value.

**Recommended Action:** Review section height/elevation value and confirm whether the value is valid for the conductor type.

**Implementation Notes:**

This rule identifies invalid or suspicious height/elevation values. The exact logic may depend on whether the conductor is overhead or underground.

For example, an overhead conductor may be expected to have a positive height above ground, while an underground conductor may use a negative value depending on Synergi conventions. This assumption should be confirmed with the sponsor.

## VR12 - Different Conductors on One Section

**Category:** Circuit Data

**Severity:** Warning

**Issue:** Different conductors on one section

**Description:** Section uses different conductors within one section definition.

**Recommended Action:** Review conductor type, size, and material fields for the section.

**Implementation Notes:**

This rule identifies sections with inconsistent conductor definitions. The implementation should compare conductor-related fields associated with the same section and flag unexpected differences.

Acceptable exceptions should be documented if the sponsor identifies valid cases.

## VR13 - Fewer Upstream Phases

**Category:** Circuit Data

**Severity:** Error

**Issue:** Fewer upstream phases

**Description:** Upstream conductor has fewer phases than downstream connection.

**Recommended Action:** Trace upstream and downstream sections and review phase assignments.

**Implementation Notes:**

This rule checks whether a downstream section or device has more phases than the upstream conductor feeding it. A complete implementation requires ordered connectivity or graph traversal so upstream and downstream relationships can be determined.

Phase values should be normalized before comparison.

## VR14 - Customer Count Missing

**Category:** Circuit Data

**Severity:** Warning

**Issue:** Customer count missing

**Description:** Customer count is missing.

**Recommended Action:** Review customer count field and populate it where expected.

**Implementation Notes:**

This rule identifies missing or blank customer count values where customer count is expected. Some records may intentionally have no customer count, so sponsor guidance may be needed to determine when the field is required.

## Maintenance Notes

1. This document should be updated whenever `rules.py` changes.
2. The rule ID, category, severity, issue, description, and recommended action should stay synchronized with the `RULES` dictionary in `rules.py`.
3. Implementation details may be more specific than the generic rule metadata, especially when a rule produces multiple issue subtypes.
4. Any sponsor-approved exceptions, tolerances, or known limitations should be added to the relevant rule section.