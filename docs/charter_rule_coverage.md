# Charter Rule Coverage

Source reviewed: `data/raw/project_charter_synergi_validation.xlsx - Validation Rules.pdf`.

The uploaded charter contains validation rules VR1 through VR14. The table below maps each charter rule to the implemented check, primary report output, diagnostic output, and known implementation notes.

| Rule ID | Charter Rule | Implementation | Issue Output Sheet | Diagnostic Output | Coverage Notes |
|---|---|---|---|---|---|
| VR1 | Unfed sections | `topology/unfed_sections.py` and open-fuse context in `checks/fuses.py` | `DisconnectedTopology` | `TopologyComponents` | Uses `InstSection.IsFed` when available; otherwise falls back to connected-component review grouped by `FeederId` when possible. A full source-rooted, phase-aware reachability pass still requires sponsor-provided source-node metadata. |
| VR2 | Loops | `topology/loops.py` | `LoopSummary`, `LoopReviewSummary` | `LoopSectionDetails`, `LoopReviewSectionDetails`, `LoopDiagnostics`, `PhysicalCycleDiagnostics`, self-loop/duplicate/parallel-section diagnostics | Detects actual or plausibly actionable operating loops from confirmed closed sections. Physical graph cycles broken by opens or phase discontinuity are diagnostics only. `main.py` passes fuse status into the operating graph and accepts `--feeder-topology-file` for RADIAL/MESHED/UNKNOWN feeder policy. |
| VR3 | Source voltage issue | `checks/source_voltage.py` | `SourceVoltageIssues` | `SourceVoltageContext` | Discovers source-like tables, adapting each table independently. Compares source nominal voltage to feeder/system or by-phase voltage evidence when both sides are available. Rows without usable expected voltage are marked `NOT_RUN` in diagnostics. |
| VR4 | Open fuses | `checks/fuses.py` | `OpenFuses` | None | Uses `FuseIsOpen` with centralized boolean normalization. |
| VR5 | Capacitor 0 rating | `checks/capacitors.py` | `CapacitorIssues` | None | Checks fixed and switched module kVAR totals for zero/missing configured reactive rating. |
| VR6 | Capacitor voltage mismatch | `checks/capacitors.py` | `CapacitorIssues` | `CapVoltageContext`, `TransformerLocations` | Compares capacitor `RatedKv` to section configuration voltage, transformer-aware voltage, or direct section voltage. Uses a 10 percent tolerance pending sponsor confirmation. |
| VR7 | Capacitor phase mismatch | `checks/capacitors.py` | `CapacitorIssues` | None | Compares capacitor connected phases to connected section phases. |
| VR8 | Regulator phase/section mismatch | `checks/regulators.py` | `RegulatorIssues` | `RegulatorContext` | Compares regulator connected phases/section/node attributes to the matched `InstSection` record. |
| VR9 | XFMR-regulator pair positioning | `checks/regulators.py` | `RegulatorIssues` | `RegulatorContext`, `TransformerLocations` | Reviews transformer/regulator ordering and regulator voltage context. Classified as Review in the rule registry. |
| VR10 | No connected kVA | `checks/loads.py` | `NoConnectedKVA` | None | Evaluates sections represented in operational load-source tables. The sample MDB uses `Loads`, with additional records in `InstLargeCust` and `InstProjLoads`; multi-year scenario tables such as `InstMymLoads` are not included by default because they duplicate the same sections by year/scenario. Uses kVA directly when available and derives apparent power from `sqrt(kW^2 + kVAR^2)` when kW/kVAR are the available basis. |
| VR11 | Section at negative height | `checks/conductorheight.py` | `ConductorHeight` | None | Uses conductor keywords to classify underground vs overhead and flags sign mismatches in `AveHeightAboveGround_MUL`. |
| VR12 | Different conductors on one section | `checks/mismatched_conductors.py` | `ConductorMismatch` | None | Uses `IdenticalPhaseConductors` as the controlling Synergi field. Sections marked as identical are not flagged solely because alternate phase conductor fields are `Unknown`; non-identical sections are checked for differing or missing active phase conductor IDs. |
| VR13 | Fewer phases upstream conductor | `checks/incorrectphases.py` | `IncorrectPhases` | None | Compares direct upstream/downstream section phase sets using `ToNodeId` to `FromNodeId`. A full graph traversal may be needed if devices interrupt section-to-section continuity. |
| VR14 | Customer count missing | `checks/customercount.py` | `CustomerCount` | None | Uses the same preferred connected-load basis as VR10 and skips `IsSpotLoad` rows when present. |

## Report Coverage

The Excel report writes:

- A consolidated `Issues` sheet containing all non-empty issue sheets.
- One issue sheet per implemented charter rule family.
- Diagnostic sheets for source voltage, capacitor voltage, transformer locations, regulator context, topology components, loop evidence, physical cycle diagnostics, self-loops, duplicate section IDs, and parallel physical sections.

## Current Sponsor-Dependent Assumptions

1. VR3, VR6, and VR9 voltage tolerances are currently 10 percent.
2. VR2 treats only configured radial feeders as Error; unknown feeder topology is Review and explicitly meshed feeders are suppressed. Supply `--feeder-topology-file` to avoid systematic under-classification.
3. VR11 underground/overhead classification is inferred from conductor-name keywords.
4. VR13 currently checks direct section adjacency, not a full device-aware upstream trace.
5. Some VR1 cases rely on `InstSection.IsFed` because source-node metadata may vary by MDB.
6. NetworkX `cycle_basis` returns an independent cycle basis, not every possible simple cycle. VR2 reports representative independent cycle evidence rather than enumerating all mathematically possible loops.
