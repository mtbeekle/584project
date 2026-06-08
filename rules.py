from dataclasses import dataclass


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    category: str
    severity: str
    issue: str
    description: str
    recommended_action: str


RULES: dict[str, RuleDefinition] = {
    "VR1": RuleDefinition(
        rule_id="VR1",
        category="Topology",
        severity="Error",
        issue="Unfed section",
        description="Section is unfed or disconnected from a valid source.",
        recommended_action="Review upstream connectivity, source path, switching status, and source assignment.",
    ),
    "VR2": RuleDefinition(
        rule_id="VR2",
        category="Topology",
        severity="Error",
        issue="Potential loop detected",
        description="Potential loop detected in feeder topology.",
        recommended_action="Review feeder connectivity and confirm whether the loop is intentional or should be corrected.",
    ),
    "VR3": RuleDefinition(
        rule_id="VR3",
        category="Component / Device",
        severity="Error",
        issue="Source voltage mismatch",
        description="Source voltage does not match expected feeder voltage.",
        recommended_action="Compare source nominal voltage against feeder, system, or connected section voltage values.",
    ),
    "VR4": RuleDefinition(
        rule_id="VR4",
        category="Component / Device",
        severity="Warning",
        issue="Open fuse",
        description="Fuse is open in converted model; review device status.",
        recommended_action="Confirm whether the fuse should be open in the normal converted model.",
    ),
    "VR5": RuleDefinition(
        rule_id="VR5",
        category="Component / Device",
        severity="Warning",
        issue="Capacitor zero or missing rating",
        description="Capacitor has zero or missing rating.",
        recommended_action="Review capacitor kVAR fields and populate a valid rating if needed.",
    ),
    "VR6": RuleDefinition(
        rule_id="VR6",
        category="Component / Device",
        severity="Error",
        issue="Capacitor voltage mismatch",
        description="Capacitor voltage mismatches connected circuit voltage.",
        recommended_action="Compare capacitor nominal voltage against the connected section or bus voltage.",
    ),
    "VR7": RuleDefinition(
        rule_id="VR7",
        category="Component / Device",
        severity="Error",
        issue="Capacitor phase mismatch",
        description="Capacitor phases do not match connected section phases.",
        recommended_action="Review capacitor connected phases and section phase designation.",
    ),
    "VR8": RuleDefinition(
        rule_id="VR8",
        category="Component / Device",
        severity="Error",
        issue="Regulator phase or section mismatch",
        description="Regulator phases or sections are mismatched.",
        recommended_action="Review regulator phase count, associated section IDs, and connected section phase designations.",
    ),
    "VR9": RuleDefinition(
        rule_id="VR9",
        category="Component / Device",
        severity="Review",
        issue="XFMR-regulator pair positioning issue",
        description="XFMR-regulator pair positioning appears inconsistent.",
        recommended_action="Review transformer/regulator adjacency and expected ordering in the converted topology.",
    ),
    "VR10": RuleDefinition(
        rule_id="VR10",
        category="Circuit Data",
        severity="Warning",
        issue="No connected kVA",
        description="Feeder or section has no connected kVA.",
        recommended_action="Confirm whether load is expected and review connected customer or load records.",
    ),
    "VR11": RuleDefinition(
        rule_id="VR11",
        category="Circuit Data",
        severity="Warning",
        issue="Section at negative height",
        description="Section has negative height or elevation value.",
        recommended_action="Review section height/elevation value and confirm whether the value is valid for the conductor type.",
    ),
    "VR12": RuleDefinition(
        rule_id="VR12",
        category="Circuit Data",
        severity="Warning",
        issue="Different conductors on one section",
        description="Section uses different conductors within one section definition.",
        recommended_action="Review conductor type, size, and material fields for the section.",
    ),
    "VR13": RuleDefinition(
        rule_id="VR13",
        category="Circuit Data",
        severity="Error",
        issue="Fewer upstream phases",
        description="Upstream conductor has fewer phases than downstream connection.",
        recommended_action="Trace upstream and downstream sections and review phase assignments.",
    ),
    "VR14": RuleDefinition(
        rule_id="VR14",
        category="Circuit Data",
        severity="Warning",
        issue="Customer count missing",
        description="Customer count is missing.",
        recommended_action="Review customer count field and populate it where expected.",
    ),
}


def get_rule(rule_id: str) -> RuleDefinition:
    try:
        return RULES[rule_id]
    except KeyError as exc:
        raise KeyError(
            f"Rule ID is not defined in the project charter rule registry: {rule_id}"
        ) from exc