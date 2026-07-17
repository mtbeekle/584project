# topology/loops.py

from collections.abc import Iterable

import pandas as pd
import networkx as nx

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    normalize_boolean_value,
    parse_phase_set,
    validate_required_columns,
)
from topology.graph_builder import (
    REQUIRED_SECTION_COLUMNS,
    build_section_graph,
    find_duplicate_section_ids,
    find_parallel_endpoint_sections,
    find_self_loop_sections,
    unordered_endpoint_pair,
    valid_section_mask,
)


CLOSED = "CLOSED"
OPEN = "OPEN"
OUT_OF_SERVICE = "OUT_OF_SERVICE"
UNKNOWN = "UNKNOWN"

RADIAL = "RADIAL"
MESHED = "MESHED"
UNKNOWN_TOPOLOGY = "UNKNOWN"

LOOP_ERROR_ISSUE = "Confirmed energized closed loop"
LOOP_WARNING_ISSUE = "Likely closed tie or cross-feeder closed connection"
LOOP_REVIEW_ISSUE = "Potential loop or meshed topology"

LOOP_DESCRIPTION = (
    "Cycle evidence is based on confirmed operating state, feeder grouping, "
    "feeder topology configuration, and phase continuity."
)
LOOP_RECOMMENDED_ACTION = (
    "Review the suspect tie or closing section, switching status, feeder/source "
    "assignment, and whether this loop is intentional."
)

OPEN_END_COLUMNS = ["IsFromEndOpen", "IsToEndOpen"]
SECTION_STATUS_COLUMNS = [
    "SectionStatus",
    "OperatingStatus",
    "Status",
    "SwitchStatus",
    "DeviceStatus",
]
OUT_OF_SERVICE_BOOLEAN_COLUMNS = [
    "IsOutOfService",
    "OutOfService",
    "IsRetired",
    "IsDeenergized",
]
IN_SERVICE_BOOLEAN_COLUMNS = ["IsInService", "InService", "Enabled", "IsEnabled"]
PHASE_COLUMNS = [
    "SectionPhases",
    "Phases",
    "Phase",
    "ConnectedPhases",
    "ConductorPhases",
]
SWITCH_ID_COLUMNS = [
    "SwitchId",
    "SwitchID",
    "DeviceId",
    "DeviceID",
    "ProtectiveDeviceId",
    "FuseId",
]
SOURCE_ID_COLUMNS = ["SourceId", "SourceID", "SourceNodeId", "SourceName", "SubstationId"]
SOURCE_BOOLEAN_TOKENS = ("SOURCE", "SUBSTATION", "FEEDERHEAD")
DER_TOKENS = ("DER", "DG", "GENERATOR", "SOLAR", "PV")
MESH_TOKENS = ("MESH", "NETWORK", "LOOP")

SUMMARY_COLUMNS = [
    "LoopID",
    "RuleID",
    "Category",
    "Severity",
    "ElementType",
    "ElementID",
    "Issue",
    "Description",
    "RecommendedAction",
    "FeederId",
    "FeederIdsInCycle",
    "FeederTopology",
    "Phase",
    "NodeIds",
    "EndpointPairs",
    "SectionIds",
    "SuspectSectionId",
    "SuspectReason",
    "SectionCount",
    "SourceCount",
    "SwitchIds",
    "UnknownStatusCount",
    "LikelyCause",
]
DETAIL_COLUMNS = [
    "LoopID",
    "Severity",
    "Issue",
    "SectionId",
    "FeederId",
    "FromNodeId",
    "ToNodeId",
    "SectionState",
    "SectionPhases",
    "SwitchIds",
    "IsSuspectSection",
]
PHYSICAL_DIAGNOSTIC_COLUMNS = [
    "DiagnosticID",
    "Reason",
    "FeederId",
    "FeederIdsInCycle",
    "Phase",
    "NodeIds",
    "EndpointPairs",
    "SectionIds",
    "OpenSectionCount",
    "OutOfServiceSectionCount",
    "UnknownStatusCount",
]


def _empty_summary() -> pd.DataFrame:
    return pd.DataFrame(columns=SUMMARY_COLUMNS)


def _empty_details() -> pd.DataFrame:
    return pd.DataFrame(columns=DETAIL_COLUMNS)


def _empty_physical_diagnostics() -> pd.DataFrame:
    return pd.DataFrame(columns=PHYSICAL_DIAGNOSTIC_COLUMNS)


def _is_blank(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _format_values(values: Iterable) -> str:
    unique_values = []
    seen = set()
    for value in values:
        if _is_blank(value):
            continue
        text = str(value).strip()
        if text not in seen:
            seen.add(text)
            unique_values.append(text)
    return ", ".join(unique_values)


def _true_value(value) -> bool:
    return normalize_boolean_value(value) is True


def _false_value(value) -> bool:
    return normalize_boolean_value(value) is False


def _canonical_status_text(value) -> str:
    return str(value).strip().upper().replace("-", "_").replace(" ", "_")


def _state_from_explicit_status(value) -> str | None:
    if _is_blank(value):
        return None

    text = _canonical_status_text(value)
    if text in {CLOSED, "CLOSE", "CLOSE_D", "SHUT"}:
        return CLOSED
    if text in {OPEN, "OPENED"}:
        return OPEN
    if text in {
        OUT_OF_SERVICE,
        "OUTOFSERVICE",
        "RETIRED",
        "DISABLED",
        "DEENERGIZED",
        "DE_ENERGIZED",
    }:
        return OUT_OF_SERVICE
    if text in {UNKNOWN, "UNK"}:
        return UNKNOWN

    return None


def _state_from_boolean_column(column: str, value) -> str | None:
    boolean_value = normalize_boolean_value(value)
    if boolean_value is None:
        return None

    normalized_column = column.upper()
    if column in OPEN_END_COLUMNS or normalized_column.endswith("ISOPEN") or "ISOPEN" in normalized_column:
        return OPEN if boolean_value else CLOSED
    if normalized_column.endswith("OPEN") and "OUT" not in normalized_column:
        return OPEN if boolean_value else CLOSED
    if "ISCLOSED" in normalized_column or normalized_column.endswith("CLOSED"):
        return CLOSED if boolean_value else OPEN
    if column in OUT_OF_SERVICE_BOOLEAN_COLUMNS:
        return OUT_OF_SERVICE if boolean_value else None
    if column in IN_SERVICE_BOOLEAN_COLUMNS:
        return OUT_OF_SERVICE if not boolean_value else None

    return None


def _state_from_column_value(column: str, value) -> str | None:
    boolean_state = _state_from_boolean_column(column, value)
    if boolean_state:
        return boolean_state

    if column in SECTION_STATUS_COLUMNS or column == "MergedDeviceStates":
        return _state_from_explicit_status(value)

    return None


def _present_columns(dataframe: pd.DataFrame, candidates: list[str]) -> list[str]:
    return [column for column in candidates if column in dataframe.columns]


def _row_switch_ids(row: pd.Series) -> str:
    values = []
    for column in SWITCH_ID_COLUMNS:
        if column in row.index:
            values.append(row[column])
    if "MergedSwitchIds" in row.index:
        values.extend(str(row["MergedSwitchIds"]).split(","))
    return _format_values(values)


def _section_phase_set(row: pd.Series) -> set[str]:
    for column in PHASE_COLUMNS:
        if column in row.index:
            phases = parse_phase_set(row[column])
            if phases:
                return phases
    return set()


def _status_values_from_row(row: pd.Series) -> list[str]:
    statuses = []
    status_columns = (
        SECTION_STATUS_COLUMNS
        + OUT_OF_SERVICE_BOOLEAN_COLUMNS
        + IN_SERVICE_BOOLEAN_COLUMNS
    )
    for column in status_columns:
        if column in row.index:
            state = _state_from_column_value(column, row[column])
            if state:
                statuses.append(state)

    if "MergedDeviceStates" in row.index:
        for value in str(row["MergedDeviceStates"]).split(","):
            state = _state_from_explicit_status(value)
            if state:
                statuses.append(state)

    return statuses


def section_operating_state(row: pd.Series) -> str:
    """
    Return CLOSED, OPEN, OUT_OF_SERVICE, or UNKNOWN for a section row.

    Status interpretation is column-aware. Boolean end-open fields can confirm
    open or closed endpoint state, while generic status strings only count when
    they explicitly say CLOSED, OPEN, OUT_OF_SERVICE, or UNKNOWN.
    """
    statuses = _status_values_from_row(row)
    end_states = [
        normalize_boolean_value(row[column])
        for column in OPEN_END_COLUMNS
        if column in row.index
    ]

    if OUT_OF_SERVICE in statuses:
        return OUT_OF_SERVICE
    if any(value is True for value in end_states):
        return OPEN
    if OPEN in statuses:
        return OPEN
    if CLOSED in statuses:
        return CLOSED
    if len(end_states) == len(OPEN_END_COLUMNS) and all(value is False for value in end_states):
        return CLOSED
    if UNKNOWN in statuses:
        return UNKNOWN
    return UNKNOWN


def merge_section_device_states(
    sections: pd.DataFrame,
    device_statuses: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge optional device-table status evidence by SectionId."""
    if device_statuses is None or device_statuses.empty:
        return sections.copy()

    validate_required_columns(device_statuses, "device_statuses", ["SectionId"])

    possible_state_columns = [
        column
        for column in device_statuses.columns
        if column != "SectionId"
        and (
            column in SECTION_STATUS_COLUMNS
            or column in OUT_OF_SERVICE_BOOLEAN_COLUMNS
            or column in IN_SERVICE_BOOLEAN_COLUMNS
            or "OPEN" in column.upper()
            or "CLOSED" in column.upper()
        )
    ]
    switch_columns = _present_columns(device_statuses, SWITCH_ID_COLUMNS)
    if not possible_state_columns and not switch_columns:
        return sections.copy()

    rows = []
    for section_id, devices in device_statuses.groupby("SectionId", dropna=False):
        states = []
        switch_ids = []
        for _, device in devices.iterrows():
            for column in possible_state_columns:
                state = _state_from_column_value(column, device[column])
                if state:
                    states.append(state)
            for column in switch_columns:
                switch_ids.append(device[column])

        rows.append(
            {
                "SectionId": section_id,
                "MergedDeviceStates": _format_values(states),
                "MergedSwitchIds": _format_values(switch_ids),
            }
        )

    device_summary = pd.DataFrame(rows)
    return sections.merge(device_summary, on="SectionId", how="left")


def annotate_section_states(
    sections: pd.DataFrame,
    device_statuses: pd.DataFrame | None = None,
) -> pd.DataFrame:
    annotated = merge_section_device_states(sections, device_statuses=device_statuses)
    annotated["SectionState"] = annotated.apply(section_operating_state, axis=1)
    annotated["SectionPhaseSet"] = annotated.apply(_section_phase_set, axis=1)
    annotated["SectionPhaseText"] = annotated["SectionPhaseSet"].map(
        lambda phases: "".join(sorted(phases))
    )
    annotated["SwitchIdsForCheck"] = annotated.apply(_row_switch_ids, axis=1)
    return annotated


def filter_closed_sections(
    sections: pd.DataFrame,
    device_statuses: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return sections with confirmed CLOSED operating state."""
    annotated = annotate_section_states(sections, device_statuses=device_statuses)
    return annotated[annotated["SectionState"] == CLOSED].copy()


def build_physical_graph(sections: pd.DataFrame) -> nx.MultiGraph:
    """Build the physical graph containing all valid section edges."""
    return build_section_graph(sections)


def build_operating_graph(sections: pd.DataFrame) -> nx.MultiGraph:
    """Build the operating graph containing only confirmed conductive sections."""
    return build_section_graph(sections[sections["SectionState"] == CLOSED])


def _normalize_feeder_topology_value(value) -> str:
    if _is_blank(value):
        return UNKNOWN_TOPOLOGY

    text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
    if text in {"RADIAL", "TRUE", "R"}:
        return RADIAL
    if text in {"MESHED", "MESH", "NETWORK", "LOOPED", "NON_RADIAL", "FALSE"}:
        return MESHED
    return UNKNOWN_TOPOLOGY


def _normalize_feeder_topology_config(feeder_topology=None) -> dict[str, str]:
    if feeder_topology is None:
        return {}

    if isinstance(feeder_topology, dict):
        return {
            str(feeder_id).strip(): _normalize_feeder_topology_value(topology)
            for feeder_id, topology in feeder_topology.items()
            if not _is_blank(feeder_id)
        }

    if isinstance(feeder_topology, pd.DataFrame):
        if "FeederId" not in feeder_topology.columns:
            return {}
        topology_column = None
        for candidate in ["FeederTopology", "Topology", "TopologyType", "IsRadial"]:
            if candidate in feeder_topology.columns:
                topology_column = candidate
                break
        if topology_column is None:
            return {}
        return {
            str(row["FeederId"]).strip(): _normalize_feeder_topology_value(row[topology_column])
            for _, row in feeder_topology.iterrows()
            if not _is_blank(row["FeederId"])
        }

    return {}


def _feeder_topology_for(feeder_id, feeder_topologies: dict[str, str]) -> str:
    if _is_blank(feeder_id):
        return UNKNOWN_TOPOLOGY
    return feeder_topologies.get(str(feeder_id).strip(), UNKNOWN_TOPOLOGY)


def _simple_cycle_edge_pairs(cycle: list) -> list[tuple[str, str]]:
    return [
        unordered_endpoint_pair(from_node, to_node)
        for from_node, to_node in zip(cycle, cycle[1:] + cycle[:1])
    ]


def _sections_for_edge_pair(sections: pd.DataFrame, edge_pair: tuple[str, str]) -> pd.DataFrame:
    from_nodes = sections["FromNodeId"].map(str).str.strip()
    to_nodes = sections["ToNodeId"].map(str).str.strip()
    first, second = edge_pair

    mask = (
        (from_nodes.eq(first) & to_nodes.eq(second))
        | (from_nodes.eq(second) & to_nodes.eq(first))
    )
    return sections[mask].copy()


def _cycle_sections(sections: pd.DataFrame, edge_pairs: list[tuple[str, str]]) -> pd.DataFrame:
    frames = [_sections_for_edge_pair(sections, edge_pair) for edge_pair in edge_pairs]
    if not frames:
        return sections.iloc[0:0].copy()
    combined = pd.concat(frames)
    return combined.loc[~combined.index.duplicated()].copy()


def _edge_signature(edge_pairs: list[tuple[str, str]]) -> tuple:
    return tuple(sorted(tuple(sorted(pair)) for pair in edge_pairs))


def _cycle_basis_for_sections(sections: pd.DataFrame) -> list[tuple[list, list[tuple[str, str]]]]:
    """
    Return NetworkX's independent cycle basis for a section graph.

    This is not an enumeration of every possible simple cycle; it is sufficient
    for VR2 diagnostics because the rule needs actionable loop evidence, not an
    exhaustive graph-theory cycle listing.
    """
    graph = nx.Graph()
    for _, row in sections[valid_section_mask(sections)].iterrows():
        graph.add_edge(row["FromNodeId"], row["ToNodeId"])

    return [
        (cycle, _simple_cycle_edge_pairs(cycle))
        for cycle in nx.cycle_basis(graph)
    ]


def _section_group_phase_status(sections: pd.DataFrame) -> str:
    if sections.empty:
        return "none"

    has_phase = sections["SectionPhaseSet"].map(bool)
    if has_phase.all():
        return "complete"
    if has_phase.any():
        return "partial"
    return "none"


def _phase_cycle_basis_for_sections(
    sections: pd.DataFrame,
) -> list[tuple[list, list[tuple[str, str]], set[str]]]:
    rows = []
    by_signature = {}

    for phase in ["A", "B", "C"]:
        phase_sections = sections[
            sections["SectionPhaseSet"].map(lambda phases: phase in phases)
        ]
        for nodes, edge_pairs in _cycle_basis_for_sections(phase_sections):
            signature = _edge_signature(edge_pairs)
            if signature not in by_signature:
                by_signature[signature] = {
                    "nodes": nodes,
                    "edge_pairs": edge_pairs,
                    "phases": set(),
                }
            by_signature[signature]["phases"].add(phase)

    for data in by_signature.values():
        rows.append((data["nodes"], data["edge_pairs"], data["phases"]))
    return rows


def _electrical_cycles_for_sections(
    sections: pd.DataFrame,
) -> list[tuple[list, list[tuple[str, str]], set[str], str]]:
    if sections.empty:
        return []

    phase_status = _section_group_phase_status(sections)
    if phase_status == "complete":
        phase_cycles = _phase_cycle_basis_for_sections(sections)
        return [
            (nodes, edge_pairs, phases, "phase")
            for nodes, edge_pairs, phases in phase_cycles
        ]

    if phase_status == "partial":
        return [
            (nodes, edge_pairs, set(), "partial_phase")
            for nodes, edge_pairs in _cycle_basis_for_sections(sections)
        ]

    return [
        (nodes, edge_pairs, set(), "unphased")
        for nodes, edge_pairs in _cycle_basis_for_sections(sections)
    ]


def _iter_feeder_groups(sections: pd.DataFrame) -> list[tuple[object, pd.DataFrame]]:
    if "FeederId" not in sections.columns:
        return [(None, sections)]

    return [
        (feeder_id, feeder_sections)
        for feeder_id, feeder_sections in sections.groupby("FeederId", dropna=False)
    ]


def _feeder_ids_in_sections(cycle_sections: pd.DataFrame) -> list[str]:
    if "FeederId" not in cycle_sections.columns:
        return []
    return sorted(
        {
            str(value).strip()
            for value in cycle_sections["FeederId"].dropna()
            if str(value).strip()
        }
    )


def _source_count(cycle_sections: pd.DataFrame) -> int:
    source_values = []
    for column in SOURCE_ID_COLUMNS:
        if column in cycle_sections.columns:
            source_values.extend(cycle_sections[column].dropna().astype(str).str.strip())

    source_count = len({value for value in source_values if value})

    for column in cycle_sections.columns:
        upper_column = str(column).upper()
        if any(token in upper_column for token in SOURCE_BOOLEAN_TOKENS + DER_TOKENS):
            source_count += int(cycle_sections[column].map(_true_value).sum())

    return source_count


def _has_intentional_mesh_evidence(cycle_sections: pd.DataFrame) -> bool:
    for column in cycle_sections.columns:
        upper_column = str(column).upper()
        if any(token in upper_column for token in MESH_TOKENS):
            values = cycle_sections[column]
            if values.map(_true_value).any():
                return True
            if values.astype(str).str.contains("mesh|network|loop", case=False, na=False).any():
                return True
    return False


def _common_phases(cycle_sections: pd.DataFrame) -> set[str]:
    phase_sets = [phase_set for phase_set in cycle_sections["SectionPhaseSet"].tolist() if phase_set]
    return set.intersection(*phase_sets) if phase_sets else set()


def _phase_text(phases: set[str], cycle_sections: pd.DataFrame) -> str:
    if phases:
        return "".join(sorted(phases))
    common_phases = _common_phases(cycle_sections)
    return "".join(sorted(common_phases)) if common_phases else "UNKNOWN"


def _section_has_tie_evidence(section: pd.Series) -> bool:
    section_text = " ".join(str(value) for value in section.values if not _is_blank(value))
    return "TIE" in section_text.upper()


def _section_has_switch_evidence(section: pd.Series) -> bool:
    return str(section.get("SwitchIdsForCheck", "")).strip() != ""


def _edge_section_records(
    cycle_sections: pd.DataFrame,
    edge_pairs: list[tuple[str, str]],
) -> list[tuple[tuple[str, str], pd.Series]]:
    records = []
    for edge_pair in edge_pairs:
        edge_sections = _sections_for_edge_pair(cycle_sections, edge_pair)
        for _, section in edge_sections.iterrows():
            records.append((edge_pair, section))
    return records


def _cross_feeder_boundary_sections(
    cycle_sections: pd.DataFrame,
    edge_pairs: list[tuple[str, str]],
) -> list[pd.Series]:
    records = _edge_section_records(cycle_sections, edge_pairs)
    boundary_sections = []

    for index, (_edge_pair, section) in enumerate(records):
        if "FeederId" not in section.index or _is_blank(section["FeederId"]):
            continue

        feeder_id = str(section["FeederId"]).strip()
        neighbor_feeders = []
        if index > 0 and "FeederId" in records[index - 1][1].index:
            neighbor_feeders.append(records[index - 1][1]["FeederId"])
        if index + 1 < len(records) and "FeederId" in records[index + 1][1].index:
            neighbor_feeders.append(records[index + 1][1]["FeederId"])

        if any(not _is_blank(value) and str(value).strip() != feeder_id for value in neighbor_feeders):
            boundary_sections.append(section)

    return boundary_sections


def _find_suspect_section(
    cycle_sections: pd.DataFrame,
    edge_pairs: list[tuple[str, str]],
) -> tuple[object, str]:
    feeder_ids = _feeder_ids_in_sections(cycle_sections)
    if len(feeder_ids) > 1 and "FeederId" in cycle_sections.columns:
        boundary_sections = _cross_feeder_boundary_sections(cycle_sections, edge_pairs)
        for section in boundary_sections:
            if _section_has_switch_evidence(section) or _section_has_tie_evidence(section):
                return section["SectionId"], "Feeder-boundary section has switch or tie evidence"
        if boundary_sections:
            return boundary_sections[0]["SectionId"], "Section lies on a feeder boundary in the cycle"

    switch_sections = cycle_sections[cycle_sections["SwitchIdsForCheck"].astype(str).str.strip().ne("")]
    if not switch_sections.empty:
        return switch_sections.iloc[0]["SectionId"], "Section has switch/device evidence"

    for _, section in cycle_sections.iterrows():
        if _section_has_tie_evidence(section):
            return section["SectionId"], "Section contains tie evidence"

    return None, "No suspect section identified"


def _cycle_record(
    loop_id: str,
    feeder_id,
    phases: set[str],
    nodes: list,
    edge_pairs: list[tuple[str, str]],
    cycle_sections: pd.DataFrame,
    severity: str,
    issue: str,
    likely_cause: str,
    feeder_topology: str,
) -> dict[str, object]:
    section_ids = cycle_sections["SectionId"].tolist()
    switch_ids = cycle_sections["SwitchIdsForCheck"].tolist()
    feeder_ids = _feeder_ids_in_sections(cycle_sections)
    suspect_section_id, suspect_reason = _find_suspect_section(cycle_sections, edge_pairs)

    return {
        "LoopID": loop_id,
        "RuleID": "VR2",
        "Category": "Topology",
        "Severity": severity,
        "ElementType": "TopologyCycle",
        "ElementID": loop_id,
        "Issue": issue,
        "Description": LOOP_DESCRIPTION,
        "RecommendedAction": LOOP_RECOMMENDED_ACTION,
        "FeederId": feeder_id if not _is_blank(feeder_id) else _format_values(feeder_ids),
        "FeederIdsInCycle": _format_values(feeder_ids),
        "FeederTopology": feeder_topology,
        "Phase": _phase_text(phases, cycle_sections),
        "NodeIds": _format_values(nodes),
        "EndpointPairs": "; ".join(f"{pair[0]}-{pair[1]}" for pair in edge_pairs),
        "SectionIds": _format_values(section_ids),
        "SuspectSectionId": suspect_section_id,
        "SuspectReason": suspect_reason,
        "SectionCount": len(section_ids),
        "SourceCount": _source_count(cycle_sections),
        "SwitchIds": _format_values(switch_ids),
        "UnknownStatusCount": int(cycle_sections["SectionState"].eq(UNKNOWN).sum()),
        "LikelyCause": likely_cause,
    }


def _detail_records(loop_record: dict[str, object], cycle_sections: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    suspect_section_id = loop_record["SuspectSectionId"]
    for _, section in cycle_sections.iterrows():
        rows.append(
            {
                "LoopID": loop_record["LoopID"],
                "Severity": loop_record["Severity"],
                "Issue": loop_record["Issue"],
                "SectionId": section["SectionId"],
                "FeederId": section["FeederId"] if "FeederId" in section.index else None,
                "FromNodeId": section["FromNodeId"],
                "ToNodeId": section["ToNodeId"],
                "SectionState": section["SectionState"],
                "SectionPhases": section["SectionPhaseText"],
                "SwitchIds": section["SwitchIdsForCheck"],
                "IsSuspectSection": section["SectionId"] == suspect_section_id,
            }
        )
    return rows


def _build_closed_operating_findings(
    sections: pd.DataFrame,
    feeder_topologies: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, set[tuple]]:
    loop_rows = []
    review_rows = []
    actionable_detail_rows = []
    review_detail_rows = []
    seen_signatures = set()
    known_non_cross_signatures = set()
    loop_counter = 1

    closed_sections = sections[sections["SectionState"] == CLOSED]

    for feeder_id, feeder_sections in _iter_feeder_groups(closed_sections):
        topology = _feeder_topology_for(feeder_id, feeder_topologies)
        if topology == MESHED:
            continue

        for nodes, edge_pairs, phases, mode in _electrical_cycles_for_sections(feeder_sections):
            signature = ("WITHIN", str(feeder_id), _edge_signature(edge_pairs))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            known_non_cross_signatures.add(signature)

            cycle_sections = _cycle_sections(sections, edge_pairs)
            if mode == "partial_phase":
                severity = "Review"
                issue = LOOP_REVIEW_ISSUE
                likely_cause = "Closed graph cycle found, but phase data is incomplete"
            elif topology == RADIAL:
                severity = "Error"
                issue = LOOP_ERROR_ISSUE
                likely_cause = "Confirmed closed phase-continuous cycle in feeder configured as radial"
            else:
                severity = "Review"
                issue = LOOP_REVIEW_ISSUE
                likely_cause = "Closed cycle found, but feeder topology is not configured as radial or meshed"

            loop_id = f"VR2-{loop_counter:04d}"
            loop_counter += 1
            record = _cycle_record(
                loop_id,
                feeder_id,
                phases,
                nodes,
                edge_pairs,
                cycle_sections,
                severity,
                issue,
                likely_cause,
                topology,
            )
            if severity == "Review":
                review_rows.append(record)
                review_detail_rows.extend(_detail_records(record, cycle_sections))
            else:
                loop_rows.append(record)
                actionable_detail_rows.extend(_detail_records(record, cycle_sections))

    if "FeederId" in closed_sections.columns:
        for nodes, edge_pairs, phases, mode in _electrical_cycles_for_sections(closed_sections):
            cycle_sections = _cycle_sections(sections, edge_pairs)
            feeder_ids = _feeder_ids_in_sections(cycle_sections)
            if len(feeder_ids) <= 1:
                continue
            if all(_feeder_topology_for(feeder_id, feeder_topologies) == MESHED for feeder_id in feeder_ids):
                continue

            signature = ("CROSS", tuple(feeder_ids), _edge_signature(edge_pairs))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            loop_id = f"VR2-{loop_counter:04d}"
            loop_counter += 1
            if mode == "partial_phase":
                severity = "Review"
                issue = LOOP_REVIEW_ISSUE
                likely_cause = "Closed cross-feeder graph cycle found, but phase data is incomplete"
                target_rows = review_rows
                target_details = review_detail_rows
            else:
                severity = "Warning"
                issue = LOOP_WARNING_ISSUE
                likely_cause = "Closed cycle uses sections from multiple feeders"
                target_rows = loop_rows
                target_details = actionable_detail_rows

            record = _cycle_record(
                loop_id,
                "CROSS_FEEDER",
                phases,
                nodes,
                edge_pairs,
                cycle_sections,
                severity,
                issue,
                likely_cause,
                "CROSS_FEEDER",
            )
            target_rows.append(record)
            target_details.extend(_detail_records(record, cycle_sections))

    return (
        pd.DataFrame(loop_rows, columns=SUMMARY_COLUMNS),
        pd.DataFrame(review_rows, columns=SUMMARY_COLUMNS),
        pd.DataFrame(actionable_detail_rows, columns=DETAIL_COLUMNS),
        pd.DataFrame(review_detail_rows, columns=DETAIL_COLUMNS),
        known_non_cross_signatures,
    )


def _physical_cycle_diagnostic_record(
    diagnostic_id: str,
    reason: str,
    feeder_id,
    phases: set[str],
    nodes: list,
    edge_pairs: list[tuple[str, str]],
    cycle_sections: pd.DataFrame,
) -> dict[str, object]:
    return {
        "DiagnosticID": diagnostic_id,
        "Reason": reason,
        "FeederId": feeder_id,
        "FeederIdsInCycle": _format_values(_feeder_ids_in_sections(cycle_sections)),
        "Phase": _phase_text(phases, cycle_sections),
        "NodeIds": _format_values(nodes),
        "EndpointPairs": "; ".join(f"{pair[0]}-{pair[1]}" for pair in edge_pairs),
        "SectionIds": _format_values(cycle_sections["SectionId"].tolist()),
        "OpenSectionCount": int(cycle_sections["SectionState"].eq(OPEN).sum()),
        "OutOfServiceSectionCount": int(cycle_sections["SectionState"].eq(OUT_OF_SERVICE).sum()),
        "UnknownStatusCount": int(cycle_sections["SectionState"].eq(UNKNOWN).sum()),
    }


def _build_non_closed_cycle_outputs(
    sections: pd.DataFrame,
    feeder_topologies: dict[str, str],
    known_finding_signatures: set[tuple],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    review_rows = []
    detail_rows = []
    diagnostic_rows = []
    seen_physical_signatures = set()
    review_counter = 1
    diagnostic_counter = 1

    def process_cycle(feeder_id, topology, nodes, edge_pairs) -> None:
        nonlocal review_counter
        nonlocal diagnostic_counter

        signature = ("PHYSICAL", str(feeder_id), _edge_signature(edge_pairs))
        if signature in seen_physical_signatures:
            return
        seen_physical_signatures.add(signature)

        cycle_sections = _cycle_sections(sections, edge_pairs)
        states = set(cycle_sections["SectionState"].dropna().astype(str))
        has_phase_data = cycle_sections["SectionPhaseSet"].map(bool).any()
        common_phases = _common_phases(cycle_sections)

        if OPEN in states or OUT_OF_SERVICE in states:
            reason = "Physical ring is broken by a confirmed open or out-of-service section"
            diagnostic_rows.append(
                _physical_cycle_diagnostic_record(
                    f"VR2-PHY-{diagnostic_counter:04d}",
                    reason,
                    feeder_id,
                    common_phases,
                    nodes,
                    edge_pairs,
                    cycle_sections,
                )
            )
            diagnostic_counter += 1
            return

        if has_phase_data and not common_phases:
            reason = "Physical ring is not phase-continuous"
            diagnostic_rows.append(
                _physical_cycle_diagnostic_record(
                    f"VR2-PHY-{diagnostic_counter:04d}",
                    reason,
                    feeder_id,
                    common_phases,
                    nodes,
                    edge_pairs,
                    cycle_sections,
                )
            )
            diagnostic_counter += 1
            return

        if UNKNOWN in states:
            finding_signature = ("WITHIN", str(feeder_id), _edge_signature(edge_pairs))
            if finding_signature in known_finding_signatures:
                return

            loop_id = f"VR2-RVW-{review_counter:04d}"
            review_counter += 1
            record = _cycle_record(
                loop_id,
                feeder_id,
                common_phases,
                nodes,
                edge_pairs,
                cycle_sections,
                "Review",
                LOOP_REVIEW_ISSUE,
                "Physical cycle has unknown status on one or more sections",
                topology,
            )
            review_rows.append(record)
            detail_rows.extend(_detail_records(record, cycle_sections))

    for feeder_id, feeder_sections in _iter_feeder_groups(sections):
        topology = _feeder_topology_for(feeder_id, feeder_topologies)
        if topology == MESHED:
            continue

        for nodes, edge_pairs in _cycle_basis_for_sections(feeder_sections):
            process_cycle(feeder_id, topology, nodes, edge_pairs)

    if "FeederId" in sections.columns:
        for nodes, edge_pairs in _cycle_basis_for_sections(sections):
            cycle_sections = _cycle_sections(sections, edge_pairs)
            feeder_ids = _feeder_ids_in_sections(cycle_sections)
            if len(feeder_ids) <= 1:
                continue
            if all(_feeder_topology_for(feeder_id, feeder_topologies) == MESHED for feeder_id in feeder_ids):
                continue
            process_cycle("CROSS_FEEDER", "CROSS_FEEDER", nodes, edge_pairs)

    return (
        pd.DataFrame(review_rows, columns=SUMMARY_COLUMNS),
        pd.DataFrame(detail_rows, columns=DETAIL_COLUMNS),
        pd.DataFrame(diagnostic_rows, columns=PHYSICAL_DIAGNOSTIC_COLUMNS),
    )


def find_loop_section_ids(graph: nx.Graph | nx.MultiGraph) -> set:
    """
    Backward-compatible helper returning SectionId values in simple graph cycles.

    Handles both nx.Graph edge attributes and nx.MultiGraph keyed edge-data
    dictionaries.
    """
    simple_graph = nx.Graph()
    simple_graph.add_nodes_from(graph.nodes)
    simple_graph.add_edges_from((from_node, to_node) for from_node, to_node in graph.edges())

    loop_section_ids = set()
    for cycle in nx.cycle_basis(simple_graph):
        for first, second in _simple_cycle_edge_pairs(cycle):
            if not graph.has_edge(first, second):
                continue
            edge_data = graph.get_edge_data(first, second)
            if not isinstance(edge_data, dict):
                continue

            if "SectionId" in edge_data:
                section_id = edge_data.get("SectionId")
                if pd.notna(section_id):
                    loop_section_ids.add(section_id)
                continue

            for data in edge_data.values():
                if isinstance(data, dict):
                    section_id = data.get("SectionId")
                    if pd.notna(section_id):
                        loop_section_ids.add(section_id)

    return loop_section_ids


def _build_loop_sections(sections: pd.DataFrame, loop_section_details: pd.DataFrame) -> pd.DataFrame:
    empty = add_rule_columns(
        sections.iloc[0:0].copy(),
        rule=get_rule("VR2"),
        element_type="Section",
        element_id="SectionId",
    )
    if loop_section_details.empty:
        return empty

    suspect_details = loop_section_details[loop_section_details["IsSuspectSection"].eq(True)]
    if suspect_details.empty:
        return empty

    loop_sections = sections[sections["SectionId"].isin(suspect_details["SectionId"])].copy()
    if loop_sections.empty:
        return empty

    detail_by_section = suspect_details.drop_duplicates("SectionId").set_index("SectionId")
    loop_sections = add_rule_columns(
        loop_sections,
        rule=get_rule("VR2"),
        element_type="Section",
        element_id="SectionId",
    )
    loop_sections["LoopIDs"] = loop_sections["SectionId"].map(
        suspect_details.groupby("SectionId")["LoopID"].apply(_format_values)
    )
    loop_sections["Severity"] = loop_sections["SectionId"].map(detail_by_section["Severity"])
    loop_sections["Issue"] = loop_sections["SectionId"].map(detail_by_section["Issue"])
    loop_sections["Description"] = LOOP_DESCRIPTION
    loop_sections["RecommendedAction"] = LOOP_RECOMMENDED_ACTION
    return loop_sections


def _build_loop_diagnostics(
    sections: pd.DataFrame,
    annotated_sections: pd.DataFrame,
    physical_graph: nx.MultiGraph,
    operating_graph: nx.MultiGraph,
    loop_summary: pd.DataFrame,
    loop_review_summary: pd.DataFrame,
    physical_cycle_diagnostics: pd.DataFrame,
    self_loops: pd.DataFrame,
    duplicate_section_ids: pd.DataFrame,
    parallel_sections: pd.DataFrame,
) -> pd.DataFrame:
    valid_count = int(valid_section_mask(sections).sum())
    state_counts = annotated_sections["SectionState"].value_counts().to_dict()
    issue_counts = pd.concat(
        [loop_summary["Severity"], loop_review_summary["Severity"]],
        ignore_index=True,
    ).value_counts().to_dict()

    rows = [
        {"Check": "Input section rows", "Count": len(sections)},
        {"Check": "Valid physical graph sections", "Count": valid_count},
        {"Check": "Physical graph nodes", "Count": physical_graph.number_of_nodes()},
        {"Check": "Physical graph edges", "Count": physical_graph.number_of_edges()},
        {"Check": "Operating graph nodes", "Count": operating_graph.number_of_nodes()},
        {"Check": "Operating graph closed edges", "Count": operating_graph.number_of_edges()},
        {"Check": "Actionable loop summary rows", "Count": len(loop_summary)},
        {"Check": "Review loop summary rows", "Count": len(loop_review_summary)},
        {"Check": "Physical cycle diagnostic rows", "Count": len(physical_cycle_diagnostics)},
        {"Check": "Self-loop sections", "Count": len(self_loops)},
        {"Check": "Duplicate SectionId rows", "Count": len(duplicate_section_ids)},
        {
            "Check": "Endpoint pairs with multiple sections",
            "Count": parallel_sections["EndpointPair"].nunique()
            if "EndpointPair" in parallel_sections.columns
            else 0,
        },
    ]

    for state in [CLOSED, OPEN, OUT_OF_SERVICE, UNKNOWN]:
        rows.append({"Check": f"Section state {state}", "Count": state_counts.get(state, 0)})

    for severity in ["Error", "Warning", "Review"]:
        rows.append({"Check": f"Cycle classification {severity}", "Count": issue_counts.get(severity, 0)})

    return pd.DataFrame(rows)


def check_loops(
    sections: pd.DataFrame,
    device_statuses: pd.DataFrame | None = None,
    feeder_topology=None,
) -> dict:
    """
    VR2 - energized closed-loop detection.

    Sponsor-facing loop_summary contains only Error and Warning findings from
    confirmed CLOSED operating sections. Ambiguous cases go to
    loop_review_summary. Open-tie and phase-discontinuous physical rings stay
    in physical_cycle_diagnostics and are not issue outputs.
    """
    validate_required_columns(sections, "sections", REQUIRED_SECTION_COLUMNS)

    feeder_topologies = _normalize_feeder_topology_config(feeder_topology)
    self_loops = find_self_loop_sections(sections)
    duplicate_section_ids = find_duplicate_section_ids(sections)
    parallel_sections = find_parallel_endpoint_sections(sections)

    annotated_sections = annotate_section_states(sections, device_statuses=device_statuses)
    physical_sections = annotated_sections[valid_section_mask(annotated_sections)].copy()

    physical_graph = build_physical_graph(physical_sections)
    operating_graph = build_operating_graph(physical_sections)

    (
        loop_summary,
        closed_review_summary,
        closed_details,
        closed_review_details,
        known_signatures,
    ) = _build_closed_operating_findings(
        physical_sections,
        feeder_topologies,
    )
    unknown_review_summary, unknown_details, physical_cycle_diagnostics = (
        _build_non_closed_cycle_outputs(
            physical_sections,
            feeder_topologies,
            known_signatures,
        )
    )
    loop_review_summary = pd.concat(
        [closed_review_summary, unknown_review_summary],
        ignore_index=True,
        sort=False,
    )
    if loop_review_summary.empty:
        loop_review_summary = _empty_summary()

    loop_review_section_details = pd.concat(
        [closed_review_details, unknown_details],
        ignore_index=True,
        sort=False,
    )
    if loop_review_section_details.empty:
        loop_review_section_details = _empty_details()

    loop_section_details = closed_details
    if loop_section_details.empty:
        loop_section_details = _empty_details()

    loop_sections = _build_loop_sections(sections, loop_section_details)
    loop_diagnostics = _build_loop_diagnostics(
        sections,
        annotated_sections,
        physical_graph,
        operating_graph,
        loop_summary,
        loop_review_summary,
        physical_cycle_diagnostics,
        self_loops,
        duplicate_section_ids,
        parallel_sections,
    )

    return {
        "loop_sections": loop_sections,
        "loop_summary": loop_summary if not loop_summary.empty else _empty_summary(),
        "loop_review_summary": loop_review_summary,
        "loop_section_details": loop_section_details,
        "loop_review_section_details": loop_review_section_details,
        "physical_cycle_diagnostics": (
            physical_cycle_diagnostics
            if not physical_cycle_diagnostics.empty
            else _empty_physical_diagnostics()
        ),
        "loop_diagnostics": loop_diagnostics,
        "topology_self_loops": self_loops,
        "topology_duplicate_section_ids": duplicate_section_ids,
        "topology_parallel_sections": parallel_sections,
    }
