import math
import re

import numpy as np
import pandas as pd

from rules import get_rule
from validation_utils import add_rule_columns, clean_column_names, parse_phase_set
from checks.capacitors import (
    SECTION_ID_COLUMNS,
    FROM_NODE_COLUMNS,
    TO_NODE_COLUMNS,
    SECTION_VOLTAGE_COLUMNS,
    build_transformer_locations,
    _build_section_node_context,
    _clean_id,
    _find_col,
    _section_context_column,
    _voltage_kv,
)


# Keep regulator voltage checking aligned with the capacitor voltage-class logic.
# A 4.16 kV vs 12.47 kV mismatch should be caught, but tiny rounding differences should not.
VR9_VOLTAGE_TOLERANCE_PCT = 10.0

REGULATOR_ID_COLUMNS = [
    "UniqueDeviceId",
    "DeviceId",
    "DeviceID",
    "RegulatorId",
    "RegulatorID",
    "Name",
    "Id",
    "ID",
]

REGULATOR_SECTION_ID_COLUMNS = [
    "SectionId",
    "SectionID",
    "ConnectedSectionId",
    "ConnectedSectionID",
    "ParentSectionId",
    "ParentSectionID",
    "LineSectionId",
    "LineSectionID",
]

REGULATOR_PHASE_COLUMNS = [
    "ConnectedPhases",
    "RegulatorPhases",
    "DevicePhases",
    "Phases",
    "Phase",
    "PhaseDesignation",
    "ControlledPhases",
    "ConnectedPhase",
]

SECTION_PHASE_COLUMNS = [
    # IMPORTANT: for VR8, this must be the real InstSection.SectionPhases field.
    # Do not fall back to generic fields like ConnectedPhases/Phases, because those
    # can contain conductor/configuration values such as ABCN and can make the
    # Excel output differ from the MDB SectionPhases column.
    "SectionPhases",
    "SectionPhase",
]

REGULATOR_VOLTAGE_COLUMNS = [
    "RatedKv",
    "RatedKV",
    "Rated kV",
    "Rated_kV",
    "RatedKvLL",
    "RatedKVLL",
    "NominalKv",
    "NominalKV",
    "NominalVoltage",
    "NominalKvll",
    "NominalKVLL",
    "RegulatorVoltage",
    "RegulatorKv",
    "RegulatorKV",
    "VoltageRating",
    "Voltage",
    "Kv",
    "KV",
    # In the Synergi MDB used for testing, the regulator voltage is embedded in
    # InstRegulators.RegulatorType values such as "3P 13.2KV 250" or
    # "1P 19.92KV 750". Keep this after explicit voltage columns so a real
    # numeric field wins when it exists.
    "RegulatorType",
    "Regulator Type",
    "Type",
]


def _empty_results() -> dict[str, pd.DataFrame]:
    return {
        "regulator_issues": pd.DataFrame(),
        "regulator_context": pd.DataFrame(),
    }


def _series_value(row: pd.Series, column: str | None):
    if not column or column not in row.index:
        return None
    return row[column]


def _raw_context_column_name(name: str) -> str:
    return f"__VR_RAW_{name}"


def _find_instsection_phase_col(sections: pd.DataFrame) -> str | None:
    """Return the actual InstSection.SectionPhases column only.

    Earlier versions allowed fallback columns such as ConnectedPhases, Phases,
    or Phase. That was too broad for VR8 because some Synergi MDBs contain
    other phase-like/conductor fields, for example ABCN, that are not the
    InstSection.SectionPhases value shown in the MDB.

    VR8 must compare:
        InstRegulators.ConnectedPhases  vs  InstSection.SectionPhases
    so this helper intentionally stays strict.
    """
    if sections is None or sections.empty:
        return None

    normalized_lookup = {_clean_id(column).replace("_", "").lower(): column for column in sections.columns}
    for candidate in ["SectionPhases", "SectionPhase"]:
        matched = normalized_lookup.get(candidate.lower())
        if matched:
            return matched
    return None


# Internal columns added before merge so the report always compares against the
# exact InstSection values, not a same-named regulator column after pandas suffixing.
RAW_SECTION_ID_COL = _raw_context_column_name("InstSectionId")
RAW_SECTION_PHASE_COL = _raw_context_column_name("InstSectionPhases")
RAW_SECTION_FROM_NODE_COL = _raw_context_column_name("InstSectionFromNode")
RAW_SECTION_TO_NODE_COL = _raw_context_column_name("InstSectionToNode")
RAW_SECTION_VOLTAGE_COL = _raw_context_column_name("InstSectionVoltage")


def _parse_regulator_phase_set(value) -> set[str]:
    """Use the shared Synergi A/B/C parser for regulator and section phases."""
    return parse_phase_set(value)


def _same_node(left: object, right: object) -> bool:
    left_id = _clean_id(left)
    right_id = _clean_id(right)
    return bool(left_id and right_id and left_id == right_id)


def _nodes_match_section(
    regulator_from_node: object,
    regulator_to_node: object,
    section_from_node: object,
    section_to_node: object,
) -> bool | None:
    """Return True/False when enough node data exists, otherwise None."""
    reg_from = _clean_id(regulator_from_node)
    reg_to = _clean_id(regulator_to_node)
    sec_from = _clean_id(section_from_node)
    sec_to = _clean_id(section_to_node)

    if reg_from and reg_to and sec_from and sec_to:
        same_direction = reg_from == sec_from and reg_to == sec_to
        reverse_direction = reg_from == sec_to and reg_to == sec_from
        return same_direction or reverse_direction

    if reg_from and sec_from and sec_to:
        return reg_from in {sec_from, sec_to}

    if reg_to and sec_from and sec_to:
        return reg_to in {sec_from, sec_to}

    return None



def _valid_kv(value: object) -> bool:
    try:
        return not pd.isna(value) and float(value) > 0
    except Exception:
        return False


def _extract_regulator_voltage_kv(value: object) -> tuple[float, str | None]:
    """Return the regulator voltage in kV plus how it was interpreted.

    Supports both numeric voltage columns and Synergi RegulatorType text such as:
        "3P 13.2KV 250"
        "1P 19.92KV 750"

    If a numeric field is in volts, _voltage_kv converts it to kV.
    """
    if value is None:
        return np.nan, None

    try:
        if pd.isna(value):
            return np.nan, None
    except Exception:
        pass

    numeric_kv = _voltage_kv(value)
    if _valid_kv(numeric_kv):
        return numeric_kv, "numeric voltage field"

    text = str(value).strip()
    if not text:
        return np.nan, None

    # Prefer values explicitly followed by kV.
    kv_matches = re.findall(r"(\d+(?:\.\d+)?)\s*k\s*v\b", text, flags=re.IGNORECASE)
    if kv_matches:
        return float(kv_matches[0]), "parsed from regulator type text"

    # Fallback: after 1P/2P/3P, the next number is usually the kV rating.
    phase_prefix = re.search(r"\b[123]\s*P\b\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if phase_prefix:
        return float(phase_prefix.group(1)), "parsed from regulator type text"

    return np.nan, None


def _candidate_line_voltages(
    base_kv: float,
    source: str,
    regulator_phase_count: int,
    section_raw_phases: object,
) -> list[tuple[float, str]]:
    """Build plausible line-voltage candidates for comparison.

    Synergi models may store a transformer side voltage as line-to-neutral for
    distribution equipment (for example 7.2 kV on a 12.47 kV feeder), while a
    3-phase regulator type may be shown as line-to-line (13.2 kV). To avoid false
    positives, compare against the direct value and the common LL/LN conversions,
    then use the closest candidate in the report.
    """
    if not _valid_kv(base_kv):
        return []

    candidates: list[tuple[float, str]] = [(float(base_kv), source)]
    raw_phase_text = "" if section_raw_phases is None else str(section_raw_phases).upper()
    has_neutral = "N" in raw_phase_text

    # For a single-phase regulator on a grounded-wye line, the regulator may be
    # rated line-to-neutral while the line may be stored line-to-line.
    if regulator_phase_count <= 1 or has_neutral:
        candidates.append((float(base_kv) / math.sqrt(3), f"{source} converted LL-to-LN"))

    # If the transformer side is stored as LN but the regulator is 3-phase, the
    # comparable line voltage may be LL.
    if regulator_phase_count >= 2:
        candidates.append((float(base_kv) * math.sqrt(3), f"{source} converted LN-to-LL"))

    # Remove duplicate near-identical candidates while keeping readable source labels.
    unique: list[tuple[float, str]] = []
    for kv, label in candidates:
        if _valid_kv(kv) and not any(abs(kv - existing_kv) < 1e-6 for existing_kv, _ in unique):
            unique.append((kv, label))
    return unique


def _select_expected_line_voltage(
    row: pd.Series,
    section_voltage_col: str | None,
    transformer_context: dict[str, object],
    regulator_phases: set[str],
    section_raw_phases: object,
) -> dict[str, object]:
    """Choose the best line voltage for VR9.

    Priority:
    1. Use the connected InstSection voltage column if the MDB has one.
    2. If the regulator is downstream of a transformer, use the transformer's
       secondary/low-side voltage.
    3. If the regulator appears upstream of a transformer, use the transformer's
       primary/high-side voltage for voltage diagnostics, while still flagging
       the position issue.
    """
    source_value = np.nan
    source_label = None
    raw_source = None

    if section_voltage_col:
        raw_source = _series_value(row, section_voltage_col)
        source_value = _voltage_kv(raw_source)
        if _valid_kv(source_value):
            source_label = "InstSection voltage"

    status = str(transformer_context.get("TransformerPositionStatus") or "")
    if not _valid_kv(source_value):
        if "downstream" in status.lower() and not transformer_context.get("TransformerPositionIssue"):
            source_value = transformer_context.get("MatchedTransformerSecondaryKv", np.nan)
            raw_source = source_value
            source_label = "matched upstream transformer secondary voltage"
        elif "upstream of xmfr" in status.lower() or "downstream of regulator" in status.lower():
            source_value = transformer_context.get("MatchedTransformerPrimaryKv", np.nan)
            raw_source = source_value
            source_label = "matched downstream transformer primary voltage"
        elif transformer_context.get("MatchedTransformerSecondaryKv") is not None:
            # Last-resort diagnostic only, useful when same-section/unclear but a transformer was matched.
            source_value = transformer_context.get("MatchedTransformerSecondaryKv", np.nan)
            raw_source = source_value
            source_label = "matched transformer secondary voltage; position unclear"

    candidates = _candidate_line_voltages(
        source_value,
        source_label or "line voltage",
        len(regulator_phases),
        section_raw_phases,
    )

    return {
        "LineVoltageRawValueForCheck": raw_source,
        "LineVoltageSourceForCheck": source_label,
        "LineVoltageBaseKvForCheck": source_value,
        "LineVoltageCandidatesForCheck": "; ".join(f"{kv:.4g} kV ({label})" for kv, label in candidates),
        "LineVoltageCandidates": candidates,
    }


def _best_voltage_match(regulator_kv: float, candidates: list[tuple[float, str]]) -> dict[str, object]:
    if not _valid_kv(regulator_kv) or not candidates:
        return {
            "ExpectedLineVoltageKvForCheck": np.nan,
            "ExpectedLineVoltageSourceForCheck": None,
            "VoltagePercentDifference": np.nan,
        }

    best_kv, best_label = min(
        candidates,
        key=lambda item: abs(float(regulator_kv) - float(item[0])) / float(item[0]) if _valid_kv(item[0]) else float("inf"),
    )
    pct = abs(float(regulator_kv) - float(best_kv)) / float(best_kv) * 100
    return {
        "ExpectedLineVoltageKvForCheck": best_kv,
        "ExpectedLineVoltageSourceForCheck": best_label,
        "VoltagePercentDifference": pct,
    }


def _build_regulator_section_context(regulators: pd.DataFrame, sections: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    regulator_id_col = _find_col(regulators, REGULATOR_ID_COLUMNS)
    regulator_section_col = _find_col(regulators, REGULATOR_SECTION_ID_COLUMNS)
    regulator_phase_col = _find_col(regulators, REGULATOR_PHASE_COLUMNS)
    regulator_from_col = _find_col(regulators, FROM_NODE_COLUMNS)
    regulator_to_col = _find_col(regulators, TO_NODE_COLUMNS)
    regulator_voltage_col = _find_col(regulators, REGULATOR_VOLTAGE_COLUMNS)

    section_id_col = _find_col(sections, SECTION_ID_COLUMNS) or "SectionId"
    section_phase_col = _find_instsection_phase_col(sections)
    section_from_col = _find_col(sections, FROM_NODE_COLUMNS)
    section_to_col = _find_col(sections, TO_NODE_COLUMNS)
    section_voltage_source_col = _find_col(sections, SECTION_VOLTAGE_COLUMNS)

    metadata = {
        "RegulatorIdColumnUsed": regulator_id_col,
        "RegulatorSectionColumnUsed": regulator_section_col,
        "RegulatorPhaseColumnUsed": regulator_phase_col,
        "RegulatorFromNodeColumnUsed": regulator_from_col,
        "RegulatorToNodeColumnUsed": regulator_to_col,
        "RegulatorVoltageColumnUsed": regulator_voltage_col,
        "SectionIdColumnUsed": section_id_col,
        "SectionPhaseColumnUsed": section_phase_col,
        "SectionFromNodeColumnUsed": section_from_col,
        "SectionToNodeColumnUsed": section_to_col,
        "SectionVoltageColumnUsed": section_voltage_source_col,
    }

    if not regulator_section_col or section_id_col not in sections.columns:
        context = regulators.copy()
        context["MatchedSectionFound"] = False
        return context, metadata

    # Copy the InstSection columns we need into unique internal names before merging.
    # This avoids a subtle bug where a regulator column with the same name, such as
    # ConnectedPhases or SectionPhases, can hide the actual InstSection value in the
    # merged dataframe/report. VR8 must compare InstRegulators.ConnectedPhases against
    # InstSection.SectionPhases.
    sections_for_merge = sections.copy()
    sections_for_merge[RAW_SECTION_ID_COL] = sections_for_merge[section_id_col]
    if section_phase_col:
        sections_for_merge[RAW_SECTION_PHASE_COL] = sections_for_merge[section_phase_col]
    if section_from_col:
        sections_for_merge[RAW_SECTION_FROM_NODE_COL] = sections_for_merge[section_from_col]
    if section_to_col:
        sections_for_merge[RAW_SECTION_TO_NODE_COL] = sections_for_merge[section_to_col]
    if section_voltage_source_col:
        sections_for_merge[RAW_SECTION_VOLTAGE_COL] = sections_for_merge[section_voltage_source_col]

    context = regulators.merge(
        sections_for_merge,
        left_on=regulator_section_col,
        right_on=section_id_col,
        how="left",
        suffixes=("", "_Section"),
        indicator=True,
    )
    context["MatchedSectionFound"] = context["_merge"].eq("both")
    context = context.drop(columns=["_merge"])

    # Use the unique raw InstSection copies for validation. The human-readable
    # metadata still tells which original MDB column was selected.
    metadata["SectionPhaseColumnUsed"] = RAW_SECTION_PHASE_COL if section_phase_col else None
    metadata["SectionFromNodeColumnUsed"] = RAW_SECTION_FROM_NODE_COL if section_from_col else None
    metadata["SectionToNodeColumnUsed"] = RAW_SECTION_TO_NODE_COL if section_to_col else None
    metadata["SectionVoltageColumnUsed"] = RAW_SECTION_VOLTAGE_COL if section_voltage_source_col else None
    metadata["InstSectionPhaseOriginalColumn"] = section_phase_col
    metadata["InstSectionFromNodeOriginalColumn"] = section_from_col
    metadata["InstSectionToNodeOriginalColumn"] = section_to_col
    metadata["InstSectionVoltageOriginalColumn"] = section_voltage_source_col

    return context, metadata


def _nearest_transformer_context(
    regulator_section_id: object,
    transformer_locations: pd.DataFrame,
    section_context: dict[str, dict[str, object]],
) -> dict[str, object]:
    result = {
        "TransformerPositionStatus": "No transformer context available",
        "TransformerPositionIssue": False,
        "MatchedTransformerId": None,
        "MatchedTransformerSectionId": None,
        "MatchedTransformerPrimaryKv": np.nan,
        "MatchedTransformerSecondaryKv": np.nan,
        "TransformerMatchType": None,
        "TransformerSourceTable": None,
        "TransformerClass": None,
    }

    if transformer_locations is None or transformer_locations.empty:
        return result

    regulator_section_id = _clean_id(regulator_section_id)
    if not regulator_section_id:
        result["TransformerPositionStatus"] = "Cannot check transformer position: regulator SectionId is blank"
        return result

    valid_transformers = transformer_locations.copy()
    if valid_transformers.empty:
        return result

    reg_context = section_context.get(regulator_section_id, {})
    reg_from_node = reg_context.get("from_node")
    reg_to_node = reg_context.get("to_node")

    def apply_match(match: pd.Series, status: str, issue: bool, match_type: str) -> dict[str, object]:
        return {
            "TransformerPositionStatus": status,
            "TransformerPositionIssue": issue,
            "MatchedTransformerId": match.get("TransformerId"),
            "MatchedTransformerSectionId": match.get("TransformerSectionId"),
            "MatchedTransformerPrimaryKv": match.get("TransformerPrimaryKv"),
            "MatchedTransformerSecondaryKv": match.get("TransformerSecondaryKv"),
            "TransformerMatchType": match_type,
            "TransformerSourceTable": match.get("TransformerSourceTable"),
            "TransformerClass": match.get("TransformerClass"),
        }

    # Same section cannot prove high/low side, so keep it as a review issue.
    direct_matches = valid_transformers[
        valid_transformers["TransformerSectionId"].astype(str).str.strip() == regulator_section_id
    ]
    if not direct_matches.empty:
        return apply_match(
            direct_matches.iloc[0],
            "Regulator and transformer are assigned to the same SectionId; downstream side is unclear",
            True,
            "Transformer on same SectionId as regulator",
        )

    # If transformer starts at regulator ToNode, regulator is upstream/high-side of transformer: issue.
    if reg_to_node:
        downstream_matches = valid_transformers[
            valid_transformers["TransformerFromNode"].astype(str).str.strip() == str(reg_to_node).strip()
        ]
        if not downstream_matches.empty:
            return apply_match(
                downstream_matches.iloc[0],
                "Transformer is immediately downstream of regulator; regulator appears upstream of XMFR",
                True,
                "Transformer immediately downstream of regulator section",
            )

    # If transformer ends at regulator FromNode, regulator is immediately downstream/low-side: pass.
    if reg_from_node:
        upstream_matches = valid_transformers[
            valid_transformers["TransformerToNode"].astype(str).str.strip() == str(reg_from_node).strip()
        ]
        if not upstream_matches.empty:
            return apply_match(
                upstream_matches.iloc[0],
                "Transformer is immediately upstream of regulator; regulator appears downstream of XMFR",
                False,
                "Transformer immediately upstream of regulator section",
            )

    # Walk upstream from the regulator section. Finding a transformer upstream is the desired condition.
    if not reg_from_node:
        result["TransformerPositionStatus"] = "Cannot check transformer position: regulator section FromNode is blank"
        return result

    sections_by_to_node: dict[str, list[str]] = {}
    for sid, context in section_context.items():
        to_node = context.get("to_node")
        if to_node:
            sections_by_to_node.setdefault(str(to_node).strip(), []).append(sid)

    current_nodes = [str(reg_from_node).strip()]
    visited_nodes: set[str] = set()
    max_depth = max(len(section_context), 1)

    for _ in range(max_depth):
        if not current_nodes:
            break

        next_nodes = []
        for node in current_nodes:
            if node in visited_nodes:
                continue
            visited_nodes.add(node)

            upstream_transformers = valid_transformers[
                valid_transformers["TransformerToNode"].astype(str).str.strip() == node
            ]
            if not upstream_transformers.empty:
                return apply_match(
                    upstream_transformers.iloc[0],
                    "Nearest transformer found upstream; regulator appears downstream of XMFR",
                    False,
                    "Nearest upstream transformer by node trace",
                )

            for upstream_section_id in sections_by_to_node.get(node, []):
                upstream_context = section_context.get(upstream_section_id, {})
                upstream_from_node = upstream_context.get("from_node")
                if upstream_from_node:
                    next_nodes.append(str(upstream_from_node).strip())

        current_nodes = next_nodes

    result["TransformerPositionStatus"] = "No upstream transformer found by node trace; review regulator position"
    result["TransformerPositionIssue"] = True
    return result


def check_regulators(regulators, sections, transformers=None, nodes=None) -> dict[str, pd.DataFrame]:
    regulators = clean_column_names(regulators)
    sections = clean_column_names(sections)
    transformers = clean_column_names(transformers) if transformers is not None else None

    if regulators.empty:
        return _empty_results()

    print("\n========================")
    print("REGULATOR COLUMNS")
    print("========================")
    print(regulators.columns.tolist())

    context, metadata = _build_regulator_section_context(regulators, sections)
    transformer_locations = build_transformer_locations(transformers, sections)
    section_context = _build_section_node_context(sections)

    regulator_id_col = metadata.get("RegulatorIdColumnUsed")
    regulator_section_col = metadata.get("RegulatorSectionColumnUsed")
    regulator_phase_col = metadata.get("RegulatorPhaseColumnUsed")
    regulator_from_col = metadata.get("RegulatorFromNodeColumnUsed")
    regulator_to_col = metadata.get("RegulatorToNodeColumnUsed")
    regulator_voltage_col = metadata.get("RegulatorVoltageColumnUsed")
    section_phase_col = metadata.get("SectionPhaseColumnUsed")
    section_from_col = metadata.get("SectionFromNodeColumnUsed")
    section_to_col = metadata.get("SectionToNodeColumnUsed")
    section_voltage_col = metadata.get("SectionVoltageColumnUsed")

    print("Regulator ID column used:", regulator_id_col)
    print("Regulator SectionId column used:", regulator_section_col)
    print("Regulator phase column used:", regulator_phase_col)
    print("Regulator voltage column used:", regulator_voltage_col)
    print("Section phase column used for VR8:", section_phase_col)
    print("Section voltage column used for VR9:", section_voltage_col)

    vr8_rows = []
    vr9_rows = []
    diagnostic_rows = []

    for _, row in context.iterrows():
        regulator_id = _series_value(row, regulator_id_col) if regulator_id_col else None
        regulator_section_id = _series_value(row, regulator_section_col) if regulator_section_col else None
        regulator_phases = _parse_regulator_phase_set(_series_value(row, regulator_phase_col)) if regulator_phase_col else set()
        section_phases = _parse_regulator_phase_set(_series_value(row, section_phase_col)) if section_phase_col else set()
        section_found = bool(row.get("MatchedSectionFound", False))

        vr8_issue_reasons = []
        if regulator_section_col and not section_found:
            vr8_issue_reasons.append("Regulator SectionId does not match any InstSection record")

        if regulator_phase_col and section_phase_col and regulator_phases and section_phases:
            if not regulator_phases.issubset(section_phases):
                vr8_issue_reasons.append("Regulator phases are not a subset of connected section phases")
        elif regulator_phase_col and section_phase_col and regulator_phases and not section_phases:
            # The MDB has no usable InstSection.SectionPhases value for the connected section.
            # Do not substitute another column; surface it for review instead.
            vr8_issue_reasons.append("Connected InstSection SectionPhases is blank or unreadable; cannot verify regulator phase alignment")

        node_match = _nodes_match_section(
            _series_value(row, regulator_from_col),
            _series_value(row, regulator_to_col),
            _series_value(row, section_from_col),
            _series_value(row, section_to_col),
        )
        if node_match is False:
            vr8_issue_reasons.append("Regulator node attributes do not align with connected section nodes")

        transformer_context = _nearest_transformer_context(
            regulator_section_id,
            transformer_locations,
            section_context,
        )

        regulator_voltage_raw = _series_value(row, regulator_voltage_col) if regulator_voltage_col else None
        regulator_kv, regulator_voltage_source = (
            _extract_regulator_voltage_kv(regulator_voltage_raw)
            if regulator_voltage_col
            else (np.nan, None)
        )

        line_voltage_context = _select_expected_line_voltage(
            row=row,
            section_voltage_col=section_voltage_col,
            transformer_context=transformer_context,
            regulator_phases=regulator_phases,
            section_raw_phases=_series_value(row, section_phase_col) if section_phase_col else None,
        )
        voltage_match = _best_voltage_match(
            regulator_kv,
            line_voltage_context.get("LineVoltageCandidates", []),
        )
        section_kv = line_voltage_context.get("LineVoltageBaseKvForCheck", np.nan)
        expected_line_kv = voltage_match.get("ExpectedLineVoltageKvForCheck", np.nan)
        expected_line_source = voltage_match.get("ExpectedLineVoltageSourceForCheck")
        voltage_percent_difference = voltage_match.get("VoltagePercentDifference", np.nan)
        voltage_status = "VR9 voltage comparison ready"
        voltage_issue = False

        if not regulator_voltage_col:
            voltage_status = "Cannot run VR9 voltage check: regulator voltage column not found"
        elif not _valid_kv(regulator_kv):
            voltage_status = "Cannot run VR9 voltage check: regulator voltage is missing, zero, or unreadable"
        elif not _valid_kv(expected_line_kv):
            voltage_status = "Cannot run VR9 voltage check: no usable line voltage from InstSection or transformer context"
        else:
            if voltage_percent_difference > VR9_VOLTAGE_TOLERANCE_PCT:
                voltage_status = "VR9 line/regulator voltage mismatch"
                voltage_issue = True
            else:
                voltage_status = "VR9 voltage pass"

        diagnostic = {
            "RegulatorId": regulator_id,
            "RegulatorSectionId": regulator_section_id,
            "MatchedSectionFound": section_found,
            "RegulatorConnectedPhasesRawValue": _series_value(row, regulator_phase_col) if regulator_phase_col else None,
            "InstSectionSectionPhasesRawValue": _series_value(row, section_phase_col) if section_phase_col else None,
            "RegulatorPhaseRawValue": _series_value(row, regulator_phase_col) if regulator_phase_col else None,
            "InstSectionPhaseRawValue": _series_value(row, section_phase_col) if section_phase_col else None,
            "SectionPhases": _series_value(row, section_phase_col) if section_phase_col else None,
            "RegulatorPhasesForCheck": "".join(sorted(regulator_phases)),
            "SectionPhasesForCheck": "".join(sorted(section_phases)),
            "VR8IssueReasons": "; ".join(vr8_issue_reasons),
            "RegulatorVoltageColumnUsed": regulator_voltage_col,
            "RegulatorVoltageRawValueForCheck": regulator_voltage_raw,
            "RegulatorVoltageKvForCheck": regulator_kv,
            "RegulatorVoltageSourceForCheck": regulator_voltage_source,
            "SectionVoltageColumnUsed": section_voltage_col,
            "SectionVoltageKvForCheck": section_kv,
            "LineVoltageRawValueForCheck": line_voltage_context.get("LineVoltageRawValueForCheck"),
            "LineVoltageSourceForCheck": line_voltage_context.get("LineVoltageSourceForCheck"),
            "LineVoltageCandidatesForCheck": line_voltage_context.get("LineVoltageCandidatesForCheck"),
            "ExpectedLineVoltageKvForCheck": expected_line_kv,
            "ExpectedLineVoltageSourceForCheck": expected_line_source,
            "VoltagePercentDifference": voltage_percent_difference,
            "VR9VoltageStatus": voltage_status,
            **metadata,
            **transformer_context,
        }
        diagnostic_rows.append(diagnostic)

        if vr8_issue_reasons:
            temp = row.copy()
            temp["RegulatorIdForCheck"] = regulator_id
            temp["RegulatorSectionIdForCheck"] = regulator_section_id
            temp["RegulatorConnectedPhasesRawValue"] = _series_value(row, regulator_phase_col) if regulator_phase_col else None
            temp["InstSectionSectionPhasesRawValue"] = _series_value(row, section_phase_col) if section_phase_col else None
            temp["RegulatorPhaseRawValue"] = _series_value(row, regulator_phase_col) if regulator_phase_col else None
            temp["InstSectionPhaseRawValue"] = _series_value(row, section_phase_col) if section_phase_col else None
            # Make the Excel SectionPhases column show the actual InstSection.SectionPhases value.
            # This prevents the report from displaying a regulator/conductor field such as ABCN
            # under a name that users expect to match InstSection in the MDB.
            temp["SectionPhases"] = _series_value(row, section_phase_col) if section_phase_col else None
            temp["RegulatorPhasesForCheck"] = "".join(sorted(regulator_phases))
            temp["SectionPhasesForCheck"] = "".join(sorted(section_phases))
            temp["VR8IssueReasons"] = "; ".join(vr8_issue_reasons)
            temp["NodesMatchSection"] = node_match
            for key, value in metadata.items():
                temp[key] = value
            vr8_rows.append(temp)

        if transformer_context.get("TransformerPositionIssue") or voltage_issue:
            temp = row.copy()
            temp["RegulatorIdForCheck"] = regulator_id
            temp["RegulatorSectionIdForCheck"] = regulator_section_id
            temp["RegulatorVoltageRawValueForCheck"] = regulator_voltage_raw
            temp["RegulatorVoltageKvForCheck"] = regulator_kv
            temp["RegulatorVoltageSourceForCheck"] = regulator_voltage_source
            temp["SectionVoltageKvForCheck"] = section_kv
            temp["LineVoltageRawValueForCheck"] = line_voltage_context.get("LineVoltageRawValueForCheck")
            temp["LineVoltageSourceForCheck"] = line_voltage_context.get("LineVoltageSourceForCheck")
            temp["LineVoltageCandidatesForCheck"] = line_voltage_context.get("LineVoltageCandidatesForCheck")
            temp["ExpectedLineVoltageKvForCheck"] = expected_line_kv
            temp["ExpectedLineVoltageSourceForCheck"] = expected_line_source
            temp["VoltagePercentDifference"] = voltage_percent_difference
            temp["VR9VoltageStatus"] = voltage_status
            temp["VR9PositionIssue"] = transformer_context.get("TransformerPositionIssue")
            for key, value in metadata.items():
                temp[key] = value
            for key, value in transformer_context.items():
                temp[key] = value
            vr9_rows.append(temp)

    vr8_issues = add_rule_columns(
        pd.DataFrame(vr8_rows),
        rule=get_rule("VR8"),
        element_type="Regulator",
        element_id="RegulatorIdForCheck",
    )
    if not vr8_issues.empty:
        vr8_issues["Description"] = vr8_issues["VR8IssueReasons"]
        vr8_issues["RecommendedAction"] = (
            "Review the regulator SectionId, regulator phases, connected section phases, and regulator/section node fields."
        )

    vr9_issues = add_rule_columns(
        pd.DataFrame(vr9_rows),
        rule=get_rule("VR9"),
        element_type="Regulator",
        element_id="RegulatorIdForCheck",
    )
    if not vr9_issues.empty:
        vr9_issues["Description"] = vr9_issues.apply(
            lambda row: (
                f"Position check: {row.get('TransformerPositionStatus')}. "
                f"Voltage check: {row.get('VR9VoltageStatus')}."
            ),
            axis=1,
        )
        vr9_issues["RecommendedAction"] = (
            "Confirm the regulator is modeled downstream of the transformer and compare regulator voltage against the connected line/section voltage."
        )

    regulator_issues = pd.concat([vr8_issues, vr9_issues], ignore_index=True, sort=False)

    print("\n========================")
    print("REGULATOR SUMMARY")
    print("========================")
    print("VR8 regulator phase/section mismatch:", len(vr8_issues))
    print("VR9 transformer position or voltage issue:", len(vr9_issues))
    print(f"Total regulator issues found: {len(regulator_issues)}")

    return {
        "regulator_issues": regulator_issues,
        "regulator_context": pd.DataFrame(diagnostic_rows),
    }
