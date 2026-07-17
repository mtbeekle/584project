import re

import numpy as np
import pandas as pd

from rules import get_rule
from validation_utils import (
    add_rule_columns,
    clean_column_names,
    parse_phase_set,
    validate_required_columns,
)


# A voltage-class mismatch such as 4.16 kV connected to 12.47 kV is a major issue.
# Keep this tolerance configurable after sponsor review.
VR6_VOLTAGE_TOLERANCE_PCT = 10.0

CAPACITOR_RATED_KV_COLUMNS = [
    "RatedKv",
    "RatedKV",
    "Rated kV",
    "Rated_kV",
    "RatedKvLL",
    "RatedKVLL",
    "Rated kVLL",
    "NominalKvll",
    "NominalKVLL",
]

SECTION_VOLTAGE_COLUMNS = [
    "SectionNominalKv",
    "NominalKv",
    "NominalKV",
    "NominalVoltage",
    "NominalKvll",
    "NominalKVLL",
    "Nominal kVLL",
    "BaseKv",
    "BaseKV",
    "BaseVoltage",
    "OperatingKv",
    "Voltage",
    "Kv",
    "KV",
]

SECTION_CONFIGURATION_COLUMNS = [
    "ConfigurationId",
    "ConfigurationID",
    "ConfigId",
    "ConfigID",
    "LineConfiguration",
    "LineConfigurationId",
    "LineConfigurationID",
]

SECTION_ID_COLUMNS = [
    "SectionId",
    "SectionID",
    "Section",
    "SectionName",
]

FROM_NODE_COLUMNS = [
    "FromNodeId",
    "FromNodeID",
    "FromNode",
    "FromBus",
    "FromBusId",
    "FromBusID",
    "SourceNodeId",
    "SourceNode",
    "Node1",
    "NodeId1",
    "NodeID1",
    "StartNode",
]

TO_NODE_COLUMNS = [
    "ToNodeId",
    "ToNodeID",
    "ToNode",
    "ToBus",
    "ToBusId",
    "ToBusID",
    "DestinationNodeId",
    "DestinationNode",
    "Node2",
    "NodeId2",
    "NodeID2",
    "EndNode",
]

TRANSFORMER_ID_COLUMNS = [
    "UniqueDeviceId",
    "DeviceId",
    "DeviceID",
    "TransformerId",
    "TransformerID",
    "Name",
    "Id",
    "ID",
]

TRANSFORMER_SECTION_ID_COLUMNS = [
    "SectionId",
    "SectionID",
    "ConnectedSectionId",
    "ConnectedSectionID",
    "ParentSectionId",
    "ParentSectionID",
]

TRANSFORMER_PRIMARY_KV_COLUMNS = [
    "PrimaryKv",
    "PrimaryKV",
    "PrimaryVoltage",
    "RatedPrimaryKv",
    "RatedPrimaryKV",
    "HighSideKv",
    "HighSideKV",
    "HighVoltage",
    "HighKv",
    "HighKV",
    "NominalPrimaryKv",
    "NominalPrimaryKV",
]

TRANSFORMER_SECONDARY_KV_COLUMNS = [
    "SecondaryKv",
    "SecondaryKV",
    "SecondaryVoltage",
    "RatedSecondaryKv",
    "RatedSecondaryKV",
    "LowSideKv",
    "LowSideKV",
    "LowVoltage",
    "LowKv",
    "LowKV",
    "NominalSecondaryKv",
    "NominalSecondaryKV",
]

TRANSFORMER_TYPE_COLUMNS = [
    "TransformerType",
    "Transformer Type",
    "Type",
    "Description",
    "DeviceType",
    "EquipmentType",
    "Name",
]

TRANSFORMER_VOLTAGE_TEXT_COLUMNS = [
    "TransformerType",
    "Transformer Type",
    "Type",
    "Description",
    "DeviceType",
    "EquipmentType",
    "Name",
    "UniqueDeviceId",
]


# =====================================================
# Generic helpers
# =====================================================


def _key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "")


def _find_col(dataframe: pd.DataFrame, names: list[str]) -> str | None:
    if dataframe is None or dataframe.empty:
        return None

    lookup = {_key(column): column for column in dataframe.columns}
    for name in names:
        matched = lookup.get(_key(name))
        if matched:
            return matched
    return None


def _num(value: object) -> float:
    if value is None:
        return np.nan

    try:
        if pd.isna(value):
            return np.nan
    except Exception:
        pass

    normalized = str(value).strip()
    if normalized == "":
        return np.nan

    normalized = normalized.replace(",", "")
    for unit in ["kV", "KV", "kv", "V"]:
        normalized = normalized.replace(unit, "")

    try:
        return float(normalized.strip())
    except Exception:
        return np.nan


def _voltage_kv(value: object) -> float:
    numeric_value = _num(value)
    if pd.isna(numeric_value):
        return np.nan

    # Synergi fields may be in volts or kV. Treat values over 1000 as volts.
    return numeric_value / 1000.0 if abs(numeric_value) > 1000 else numeric_value



def _parse_configuration_voltage(value: object) -> dict[str, object]:
    """Extract voltage level from InstSection.ConfigurationId-style text.

    Common Synergi configuration examples include strings like:
        "12.5/7.2 kV cross arm C1"
        "12.47/7.2KV"
        "13.2 kV overhead"

    For a pair, the first value is treated as line-to-line kV and the second
    value as line-to-neutral kV because that is how values such as 12.5/7.2 kV
    are normally written in this MDB.
    """
    result = {
        "ConfigurationVoltageRawValue": value,
        "ConfigurationVoltageRawMatch": None,
        "ConfigurationVoltageLLKv": np.nan,
        "ConfigurationVoltageLNKv": np.nan,
    }

    if value is None:
        return result

    try:
        if pd.isna(value):
            return result
    except Exception:
        pass

    text = str(value).strip()
    if not text:
        return result

    pair_pattern = re.compile(
        r"(?P<ll>\d+(?:\.\d+)?)\s*(?:k\s*v)?\s*/\s*"
        r"(?P<ln>\d+(?:\.\d+)?)\s*(?:k\s*v)?",
        re.IGNORECASE,
    )
    pair_match = pair_pattern.search(text)
    if pair_match:
        ll_kv = float(pair_match.group("ll"))
        ln_kv = float(pair_match.group("ln"))
        result["ConfigurationVoltageRawMatch"] = pair_match.group(0)
        result["ConfigurationVoltageLLKv"] = _voltage_kv(ll_kv)
        result["ConfigurationVoltageLNKv"] = _voltage_kv(ln_kv)
        return result

    single_match = re.search(r"(?P<kv>\d+(?:\.\d+)?)\s*k\s*v\b", text, re.IGNORECASE)
    if single_match:
        kv = _voltage_kv(float(single_match.group("kv")))
        result["ConfigurationVoltageRawMatch"] = single_match.group(0)
        result["ConfigurationVoltageLLKv"] = kv

    return result


def _expected_configuration_kv_for_capacitor(
    config_info: dict[str, object],
    capacitor_phases: set[str],
) -> tuple[float, str | None]:
    """Choose LL or LN configuration voltage using capacitor phase count.

    If the capacitor is connected to one phase, use the LN value when present.
    If it is connected to two or three phases, use the LL value when present.
    Fallbacks are included so that a single-value configuration can still be used.
    """
    ll_kv = config_info.get("ConfigurationVoltageLLKv", np.nan)
    ln_kv = config_info.get("ConfigurationVoltageLNKv", np.nan)
    phase_count = len(capacitor_phases)

    if phase_count <= 1:
        if _valid_kv(ln_kv):
            return float(ln_kv), "InstSection.ConfigurationId line-to-neutral voltage"
        if _valid_kv(ll_kv):
            return float(ll_kv), "InstSection.ConfigurationId voltage"

    if _valid_kv(ll_kv):
        return float(ll_kv), "InstSection.ConfigurationId line-to-line voltage"
    if _valid_kv(ln_kv):
        return float(ln_kv), "InstSection.ConfigurationId line-to-neutral voltage"

    return np.nan, None

def _clean_id(value: object) -> str | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    text = str(value).strip()
    return text if text else None


def _section_context_column(
    source_column: str,
    capacitors: pd.DataFrame,
    context: pd.DataFrame,
) -> str:
    suffixed_column = f"{source_column}_Section"
    if source_column in capacitors.columns and suffixed_column in context.columns:
        return suffixed_column

    return source_column


def _is_active(value: object) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    if isinstance(value, bool):
        return value

    return str(value).strip().upper() in {
        "1",
        "TRUE",
        "T",
        "YES",
        "Y",
        "ON",
        "ACTIVE",
        "ENABLED",
        "CLOSED",
    }


# =====================================================
# Capacitor rating helpers
# =====================================================


def _fixed_kvar(row: pd.Series) -> float:
    total = 0.0
    for column in ["FixedKvarPhase1", "FixedKvarPhase2", "FixedKvarPhase3"]:
        if column not in row.index:
            continue

        value = _num(row[column])
        if not pd.isna(value):
            total += value

    return total


def _module_kvar_per_phase(row: pd.Series) -> float:
    total = 0.0
    for index in range(1, 10):
        kvar_column = f"Module{index}KvarPerPhase"
        active_column = f"Module{index}Activated"

        if kvar_column not in row.index:
            continue

        kvar_value = _num(row[kvar_column])
        if pd.isna(kvar_value):
            kvar_value = 0.0

        if active_column in row.index:
            if _is_active(row[active_column]):
                total += kvar_value
        else:
            total += kvar_value

    return total


def _build_capacitor_totals(row: pd.Series) -> dict[str, float]:
    fixed_kvar = _fixed_kvar(row)
    module_kvar_per_phase = _module_kvar_per_phase(row)
    connected_phases = (
        parse_phase_set(row["ConnectedPhases"])
        if "ConnectedPhases" in row.index
        else set()
    )
    switched_phase_count = len(connected_phases) if connected_phases else 3
    switched_kvar = module_kvar_per_phase * switched_phase_count
    return {
        "TotalFixedKvar": fixed_kvar,
        "TotalModuleKvarPerPhase": module_kvar_per_phase,
        "TotalSwitchedPhaseCount": switched_phase_count,
        "TotalSwitchedKvar": switched_kvar,
        "TotalKvar": fixed_kvar + switched_kvar,
    }


# =====================================================
# Transformer-aware VR6 helpers
# =====================================================


def _valid_kv(value: object) -> bool:
    return not pd.isna(value) and float(value) > 0


def _pick_transformer_expected_kv(
    primary_kv: float,
    secondary_kv: float,
    capacitor_side: str | None = None,
) -> float:
    """Pick the transformer voltage that corresponds to the capacitor side."""
    side = (capacitor_side or "").lower()

    if "high" in side and _valid_kv(primary_kv):
        return primary_kv

    if "low" in side and _valid_kv(secondary_kv):
        return secondary_kv

    # If side is not known, prefer low-side only as a diagnostic fallback.
    if _valid_kv(secondary_kv):
        return secondary_kv

    if _valid_kv(primary_kv):
        return primary_kv

    return np.nan


def _parse_transformer_voltage_pair(value: object) -> tuple[float, float, str | None]:
    """
    Parse voltage pairs embedded in text such as:
    - PM 115/34.5 30MVA
    - PM 69/12.47 10MVA
    - 1P 19.9/7.2 500
    - DT 7.6kV / 240V

    Returns high-side kV, low-side kV, and the raw matched text.
    """
    if value is None:
        return np.nan, np.nan, None

    try:
        if pd.isna(value):
            return np.nan, np.nan, None
    except Exception:
        pass

    text = str(value)
    pattern = re.compile(
        r"(?P<left>\d+(?:\.\d+)?)\s*(?P<left_unit>kv|v)?\s*/\s*"
        r"(?P<right>\d+(?:\.\d+)?)\s*(?P<right_unit>kv|v)?",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return np.nan, np.nan, None

    left = float(match.group("left"))
    right = float(match.group("right"))
    left_unit = (match.group("left_unit") or "kv").lower()
    right_unit = (match.group("right_unit") or "kv").lower()

    if left_unit == "v":
        left /= 1000.0
    if right_unit == "v":
        right /= 1000.0

    # If no unit was present and the secondary side looks like 240 or 480,
    # treat it as volts instead of kV.
    if right_unit == "kv" and right >= 100:
        right /= 1000.0

    high_side = max(left, right)
    low_side = min(left, right)
    return high_side, low_side, match.group(0)


def _extract_transformer_voltage_from_text(
    row: pd.Series,
    text_columns: list[str],
) -> tuple[float, float, str | None, str | None]:
    for column in text_columns:
        if column not in row.index:
            continue
        high_kv, low_kv, raw_match = _parse_transformer_voltage_pair(row[column])
        if _valid_kv(high_kv) and _valid_kv(low_kv):
            return high_kv, low_kv, column, raw_match
    return np.nan, np.nan, None, None


def _classify_transformer_type(value: object, source_table: object = None) -> str:
    text = f"{source_table or ''} {value or ''}".upper()

    if "DTRANS" in text or "DT " in text or text.strip().startswith("DT"):
        return "Distribution transformer"

    if "SUBSTATION" in text or "MVA" in text or "PM " in text or text.strip().startswith("PM"):
        return "Substation / power transformer"

    if "PRIMARY" in text or "XFMR" in text or "TRANSFORMER" in text:
        return "Primary transformer"

    if "TRANLINE" in text or "TRANVERT" in text:
        return "Transmission transformer-related table"

    return "Unknown transformer type"


def build_transformer_locations(transformers: pd.DataFrame | None, sections: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes transformer records so VR6 can understand where transformers are.

    This function is intentionally tolerant of schema differences. It tries to find:
    - transformer ID
    - transformer section ID
    - transformer from/to nodes
    - primary and secondary kV
    """
    if transformers is None or transformers.empty:
        return pd.DataFrame()

    transformers = clean_column_names(transformers)
    sections = clean_column_names(sections)

    transformer_id_col = _find_col(transformers, TRANSFORMER_ID_COLUMNS)
    transformer_section_col = _find_col(transformers, TRANSFORMER_SECTION_ID_COLUMNS)
    transformer_from_col = _find_col(transformers, FROM_NODE_COLUMNS)
    transformer_to_col = _find_col(transformers, TO_NODE_COLUMNS)
    primary_kv_col = _find_col(transformers, TRANSFORMER_PRIMARY_KV_COLUMNS)
    secondary_kv_col = _find_col(transformers, TRANSFORMER_SECONDARY_KV_COLUMNS)
    transformer_type_col = _find_col(transformers, TRANSFORMER_TYPE_COLUMNS)
    voltage_text_cols = [
        column for column in TRANSFORMER_VOLTAGE_TEXT_COLUMNS
        if column in transformers.columns
    ]

    section_id_col = _find_col(sections, SECTION_ID_COLUMNS) or "SectionId"
    section_from_col = _find_col(sections, FROM_NODE_COLUMNS)
    section_to_col = _find_col(sections, TO_NODE_COLUMNS)

    section_node_lookup: dict[str, tuple[str | None, str | None]] = {}
    if section_id_col in sections.columns:
        for _, section_row in sections.iterrows():
            sid = _clean_id(section_row[section_id_col])
            if not sid:
                continue
            from_node = _clean_id(section_row[section_from_col]) if section_from_col else None
            to_node = _clean_id(section_row[section_to_col]) if section_to_col else None
            section_node_lookup[sid] = (from_node, to_node)

    rows = []
    for idx, row in transformers.iterrows():
        transformer_id = (
            _clean_id(row[transformer_id_col])
            if transformer_id_col
            else f"Transformer_Row_{idx}"
        )
        section_id = _clean_id(row[transformer_section_col]) if transformer_section_col else None

        from_node = _clean_id(row[transformer_from_col]) if transformer_from_col else None
        to_node = _clean_id(row[transformer_to_col]) if transformer_to_col else None

        # If the transformer table only references a section, borrow that section's nodes.
        if section_id and (not from_node or not to_node):
            section_from_node, section_to_node = section_node_lookup.get(section_id, (None, None))
            from_node = from_node or section_from_node
            to_node = to_node or section_to_node

        primary_kv = _voltage_kv(row[primary_kv_col]) if primary_kv_col else np.nan
        secondary_kv = _voltage_kv(row[secondary_kv_col]) if secondary_kv_col else np.nan

        parsed_high_kv, parsed_low_kv, parsed_from_col, parsed_raw = (
            _extract_transformer_voltage_from_text(row, voltage_text_cols)
        )

        # Prefer explicit voltage columns when present; otherwise use parsed text.
        if not _valid_kv(primary_kv) and _valid_kv(parsed_high_kv):
            primary_kv = parsed_high_kv
        if not _valid_kv(secondary_kv) and _valid_kv(parsed_low_kv):
            secondary_kv = parsed_low_kv

        transformer_type_raw = row[transformer_type_col] if transformer_type_col else None
        source_table = row["TransformerSourceTable"] if "TransformerSourceTable" in row.index else None

        rows.append(
            {
                "TransformerId": transformer_id,
                "TransformerSourceTable": source_table,
                "TransformerSectionId": section_id,
                "TransformerFromNode": from_node,
                "TransformerToNode": to_node,
                "TransformerPrimaryKv": primary_kv,
                "TransformerSecondaryKv": secondary_kv,
                "TransformerVoltageRatioRaw": parsed_raw,
                "TransformerVoltageParsedFromColumn": parsed_from_col,
                "TransformerTypeRaw": transformer_type_raw,
                "TransformerClass": _classify_transformer_type(transformer_type_raw, source_table),
                "TransformerIdColumnUsed": transformer_id_col,
                "TransformerSectionColumnUsed": transformer_section_col,
                "TransformerFromNodeColumnUsed": transformer_from_col,
                "TransformerToNodeColumnUsed": transformer_to_col,
                "TransformerPrimaryKvColumnUsed": primary_kv_col,
                "TransformerSecondaryKvColumnUsed": secondary_kv_col,
                "TransformerTypeColumnUsed": transformer_type_col,
            }
        )

    return pd.DataFrame(rows)


def _build_section_node_context(sections: pd.DataFrame) -> dict[str, dict[str, object]]:
    section_id_col = _find_col(sections, SECTION_ID_COLUMNS) or "SectionId"
    section_from_col = _find_col(sections, FROM_NODE_COLUMNS)
    section_to_col = _find_col(sections, TO_NODE_COLUMNS)
    section_voltage_col = _find_col(sections, SECTION_VOLTAGE_COLUMNS)
    section_configuration_col = _find_col(sections, SECTION_CONFIGURATION_COLUMNS)

    context = {}
    if section_id_col not in sections.columns:
        return context

    for _, row in sections.iterrows():
        section_id = _clean_id(row[section_id_col])
        if not section_id:
            continue

        context[section_id] = {
            "from_node": _clean_id(row[section_from_col]) if section_from_col else None,
            "to_node": _clean_id(row[section_to_col]) if section_to_col else None,
            "section_voltage_kv": _voltage_kv(row[section_voltage_col]) if section_voltage_col else np.nan,
            "section_voltage_column": section_voltage_col,
            "section_configuration_raw": row[section_configuration_col] if section_configuration_col else None,
            "section_configuration_column": section_configuration_col,
        }

    return context


def _match_to_result(match: pd.Series, match_type: str, side: str) -> dict[str, object]:
    return {
        "TransformerAwareVoltageUsed": True,
        "TransformerMatchType": match_type,
        "MatchedTransformerId": match["TransformerId"],
        "MatchedTransformerSectionId": match["TransformerSectionId"],
        "MatchedTransformerPrimaryKv": match["TransformerPrimaryKv"],
        "MatchedTransformerSecondaryKv": match["TransformerSecondaryKv"],
        "MatchedTransformerExpectedKv": _pick_transformer_expected_kv(
            match["TransformerPrimaryKv"],
            match["TransformerSecondaryKv"],
            side,
        ),
        "CapacitorSideOfTransformer": side,
        "TransformerSourceTable": match.get("TransformerSourceTable"),
        "TransformerClass": match.get("TransformerClass"),
        "TransformerVoltageRatioRaw": match.get("TransformerVoltageRatioRaw"),
    }


def _find_transformer_for_capacitor_section(
    capacitor_section_id: object,
    transformer_locations: pd.DataFrame,
    section_context: dict[str, dict[str, object]],
) -> dict[str, object]:
    """
    Returns the most relevant transformer for a capacitor section.

    Priority:
    1. Transformer directly assigned to the same SectionId. Side is marked unknown.
    2. Transformer immediately downstream of capacitor section. Capacitor is high-side/upstream.
    3. Transformer immediately upstream of capacitor section. Capacitor is low-side/downstream.
    4. Nearest upstream transformer by following section from-node -> upstream section to-node.

    This assumes section FromNode -> ToNode generally follows source -> load.
    If the MDB uses different direction conventions, the diagnostic columns expose
    the chosen transformer and side classification for engineering review.
    """
    result = {
        "TransformerAwareVoltageUsed": False,
        "TransformerMatchType": None,
        "MatchedTransformerId": None,
        "MatchedTransformerSectionId": None,
        "MatchedTransformerPrimaryKv": np.nan,
        "MatchedTransformerSecondaryKv": np.nan,
        "MatchedTransformerExpectedKv": np.nan,
        "CapacitorSideOfTransformer": None,
        "TransformerSourceTable": None,
        "TransformerClass": None,
        "TransformerVoltageRatioRaw": None,
    }

    if transformer_locations is None or transformer_locations.empty:
        return result

    cap_section_id = _clean_id(capacitor_section_id)
    if not cap_section_id:
        return result

    valid_transformers = transformer_locations.dropna(
        subset=["TransformerPrimaryKv", "TransformerSecondaryKv"],
        how="all",
    )
    if valid_transformers.empty:
        return result

    # 1. Direct section match. This proves association, but not physical side.
    direct_matches = valid_transformers[
        valid_transformers["TransformerSectionId"].astype(str).str.strip() == cap_section_id
    ]
    if not direct_matches.empty:
        match = direct_matches.iloc[0]
        result.update(
            _match_to_result(
                match,
                "Transformer on same SectionId",
                "Same SectionId as transformer - side unknown",
            )
        )
        return result

    cap_context = section_context.get(cap_section_id, {})
    cap_from_node = cap_context.get("from_node")
    cap_to_node = cap_context.get("to_node")

    # 2. Transformer immediately downstream: capacitor sits on transformer high side.
    if cap_to_node:
        downstream_matches = valid_transformers[
            valid_transformers["TransformerFromNode"].astype(str).str.strip()
            == str(cap_to_node).strip()
        ]
        if not downstream_matches.empty:
            match = downstream_matches.iloc[0]
            result.update(
                _match_to_result(
                    match,
                    "Transformer immediately downstream of capacitor section",
                    "High side / upstream of transformer",
                )
            )
            return result

    # 3. Transformer immediately upstream: capacitor sits on transformer low side.
    if cap_from_node:
        upstream_matches = valid_transformers[
            valid_transformers["TransformerToNode"].astype(str).str.strip()
            == str(cap_from_node).strip()
        ]
        if not upstream_matches.empty:
            match = upstream_matches.iloc[0]
            result.update(
                _match_to_result(
                    match,
                    "Transformer immediately upstream of capacitor section",
                    "Low side / downstream of transformer",
                )
            )
            return result

    # 4. Nearest upstream transformer by walking from capacitor from-node upstream.
    if not cap_from_node:
        return result

    sections_by_to_node: dict[str, list[str]] = {}
    for sid, context in section_context.items():
        to_node = context.get("to_node")
        if to_node:
            sections_by_to_node.setdefault(str(to_node).strip(), []).append(sid)

    current_nodes = [str(cap_from_node).strip()]
    visited_nodes = set()
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
                match = upstream_transformers.iloc[0]
                result.update(
                    _match_to_result(
                        match,
                        "Nearest upstream transformer by node trace",
                        "Low side / downstream of transformer",
                    )
                )
                return result

            for upstream_section_id in sections_by_to_node.get(node, []):
                upstream_context = section_context.get(upstream_section_id, {})
                upstream_from_node = upstream_context.get("from_node")
                if upstream_from_node:
                    next_nodes.append(str(upstream_from_node).strip())

        current_nodes = next_nodes

    return result

def _expected_voltage_for_vr6(
    row: pd.Series,
    section_voltage_column: str | None,
    section_configuration_column: str | None,
    transformer_locations: pd.DataFrame,
    section_context: dict[str, dict[str, object]],
) -> dict[str, object]:
    transformer_match = _find_transformer_for_capacitor_section(
        row["SectionId"] if "SectionId" in row.index else None,
        transformer_locations,
        section_context,
    )

    section_kv = _voltage_kv(row[section_voltage_column]) if section_voltage_column else np.nan

    capacitor_phases = (
        parse_phase_set(row["ConnectedPhases"])
        if "ConnectedPhases" in row.index
        else set()
    )

    configuration_raw = row[section_configuration_column] if section_configuration_column else None
    configuration_info = _parse_configuration_voltage(configuration_raw)
    configuration_expected_kv, configuration_source = _expected_configuration_kv_for_capacitor(
        configuration_info,
        capacitor_phases,
    )

    # Preferred voltage source order:
    # 1. InstSection.ConfigurationId, because in this MDB it often contains values
    #    such as "12.5/7.2 kV cross arm C1" even when InstSection has no direct
    #    voltage column.
    # 2. Transformer-aware voltage, based on whether the capacitor is upstream or
    #    downstream of the matched transformer.
    # 3. Direct InstSection voltage column, only if such a column exists.
    if _valid_kv(configuration_expected_kv):
        expected_kv = configuration_expected_kv
        voltage_source = configuration_source
    elif transformer_match["TransformerAwareVoltageUsed"] and _valid_kv(transformer_match["MatchedTransformerExpectedKv"]):
        expected_kv = transformer_match["MatchedTransformerExpectedKv"]
        side = transformer_match.get("CapacitorSideOfTransformer") or "side not classified"
        voltage_source = f"Transformer-aware voltage ({side})"
    else:
        expected_kv = section_kv
        voltage_source = "Connected section voltage" if section_voltage_column else None

    return {
        "ExpectedVoltageKvForCheck": expected_kv,
        "SectionVoltageKvForCheck": section_kv,
        "ExpectedVoltageSource": voltage_source,
        "SectionConfigurationColumnUsed": section_configuration_column,
        "SectionConfigurationRawValueForCheck": configuration_raw,
        **configuration_info,
        **transformer_match,
    }


# =====================================================
# Main capacitor checks
# =====================================================


def check_capacitors(capacitors, sections, transformers=None, nodes=None):
    capacitors = clean_column_names(capacitors)
    sections = clean_column_names(sections)
    transformers = clean_column_names(transformers) if transformers is not None else None

    results = {}

    validate_required_columns(
        capacitors,
        "capacitors",
        [
            "SectionId",
            "UniqueDeviceId",
            "ConnectedPhases",
            "FixedKvarPhase1",
            "FixedKvarPhase2",
            "FixedKvarPhase3",
        ],
    )
    validate_required_columns(
        sections,
        "sections",
        ["SectionId", "SectionPhases"],
    )

    print("\n========================")
    print("CAPACITOR COLUMNS")
    print("========================")
    print(capacitors.columns.tolist())

    rated_kv_column = _find_col(capacitors, CAPACITOR_RATED_KV_COLUMNS)
    print("RatedKv column used:", rated_kv_column)

    transformer_locations = build_transformer_locations(transformers, sections)
    section_context = _build_section_node_context(sections)

    print("\n========================")
    print("TRANSFORMER DISCOVERY")
    print("========================")
    if transformer_locations.empty:
        print("No transformer table was provided, or no transformer records were found.")
    else:
        print("Transformers found:", len(transformer_locations))
        print("Transformer location columns:")
        print(
            transformer_locations[
                [
                    "TransformerIdColumnUsed",
                    "TransformerSectionColumnUsed",
                    "TransformerFromNodeColumnUsed",
                    "TransformerToNodeColumnUsed",
                    "TransformerPrimaryKvColumnUsed",
                    "TransformerSecondaryKvColumnUsed",
                ]
            ].head(1).to_dict("records")
        )

    capacitor_phase_check = capacitors.merge(
        sections,
        on="SectionId",
        how="left",
        suffixes=("", "_Section"),
    )

    section_voltage_source_column = _find_col(sections, SECTION_VOLTAGE_COLUMNS)
    section_voltage_column = (
        _section_context_column(
            section_voltage_source_column,
            capacitors,
            capacitor_phase_check,
        )
        if section_voltage_source_column
        else None
    )

    section_configuration_source_column = _find_col(sections, SECTION_CONFIGURATION_COLUMNS)
    section_configuration_column = (
        _section_context_column(
            section_configuration_source_column,
            capacitors,
            capacitor_phase_check,
        )
        if section_configuration_source_column
        else None
    )

    print("Section voltage column used:", section_voltage_column)
    print("Section configuration column used for voltage:", section_configuration_column)

    # ==================================================
    # VR7: PHASE MISMATCH CHECK
    # ==================================================

    phase_mismatch_rows = []

    for _, row in capacitor_phase_check.iterrows():
        cap_phases = parse_phase_set(row["ConnectedPhases"])
        line_phases = parse_phase_set(row["SectionPhases"])

        if cap_phases and line_phases and not cap_phases.issubset(line_phases):
            temp = row.copy()
            temp["CapacitorPhasesForCheck"] = "".join(sorted(cap_phases))
            temp["SectionPhasesForCheck"] = "".join(sorted(line_phases))
            for key, value in _build_capacitor_totals(row).items():
                temp[key] = value
            phase_mismatch_rows.append(temp)

    phase_mismatches = add_rule_columns(
        pd.DataFrame(phase_mismatch_rows),
        rule=get_rule("VR7"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    # ==================================================
    # VR5: ZERO OR MISSING KVAR RATING
    # ==================================================

    capacitor_rating_issue_rows = []

    for _, row in capacitors.iterrows():
        totals = _build_capacitor_totals(row)
        if totals["TotalFixedKvar"] > 0 or totals["TotalModuleKvarPerPhase"] > 0:
            continue

        temp = row.copy()
        for key, value in totals.items():
            temp[key] = value
        capacitor_rating_issue_rows.append(temp)

    capacitor_rating_issues = add_rule_columns(
        pd.DataFrame(capacitor_rating_issue_rows),
        rule=get_rule("VR5"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    # ==================================================
    # VR6 subissue: MISSING OR ZERO RATEDKV
    # ==================================================

    capacitor_missing_rated_kv_rows = []

    if rated_kv_column:
        for _, row in capacitors.iterrows():
            rated_kv_numeric = _num(row[rated_kv_column])
            if not pd.isna(rated_kv_numeric) and rated_kv_numeric > 0:
                continue

            temp = row.copy()
            temp["RatedKvColumnUsed"] = rated_kv_column
            temp["RatedKvRaw"] = row[rated_kv_column]
            temp["RatedKvNumeric"] = rated_kv_numeric
            for key, value in _build_capacitor_totals(row).items():
                temp[key] = value
            capacitor_missing_rated_kv_rows.append(temp)

    capacitor_missing_rated_kv_issues = add_rule_columns(
        pd.DataFrame(capacitor_missing_rated_kv_rows),
        rule=get_rule("VR6"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    if not capacitor_missing_rated_kv_issues.empty:
        capacitor_missing_rated_kv_issues["Severity"] = "Review"
        capacitor_missing_rated_kv_issues["Issue"] = "Capacitor RatedKv is missing or zero"
        capacitor_missing_rated_kv_issues["Description"] = (
            "Capacitor RatedKv is blank, missing, or zero in the source data."
        )
        capacitor_missing_rated_kv_issues["RecommendedAction"] = (
            "Check the RatedKv column for this capacitor and populate a valid kV value if needed."
        )

    # ==================================================
    # VR6: TRANSFORMER-AWARE VOLTAGE MISMATCH
    # ==================================================

    capacitor_voltage_issue_rows = []
    capacitor_voltage_context_rows = []

    # Build this diagnostic for every capacitor, even when no VR6 mismatch exists.
    # This is the tab reviewers use to confirm whether VR6 compared the capacitor
    # RatedKv against the connected section voltage or a transformer-side voltage.
    for _, row in capacitor_phase_check.iterrows():
        capacitor_kv = _voltage_kv(row[rated_kv_column]) if rated_kv_column else np.nan
        voltage_context = _expected_voltage_for_vr6(
            row,
            section_voltage_column,
            section_configuration_column,
            transformer_locations,
            section_context,
        )
        expected_kv = voltage_context["ExpectedVoltageKvForCheck"]

        percent_difference = np.nan
        diagnostic_status = "VR6 comparison ready"

        if not rated_kv_column:
            diagnostic_status = "Cannot run VR6: capacitor RatedKv column not found"
        elif (
            not section_voltage_column
            and not section_configuration_column
            and not voltage_context.get("TransformerAwareVoltageUsed")
        ):
            diagnostic_status = "Cannot run VR6: no section voltage, configuration voltage, or transformer voltage context"
        elif pd.isna(capacitor_kv) or capacitor_kv <= 0:
            diagnostic_status = "Cannot run VR6: capacitor RatedKv is missing or zero"
        elif pd.isna(expected_kv) or expected_kv <= 0:
            diagnostic_status = "Cannot run VR6: expected voltage is missing or zero"
        else:
            percent_difference = abs(capacitor_kv - expected_kv) / expected_kv * 100
            if percent_difference > VR6_VOLTAGE_TOLERANCE_PCT:
                diagnostic_status = "VR6 mismatch"
            else:
                diagnostic_status = "VR6 pass"

        context_row = {
            "CapacitorId": row.get("UniqueDeviceId"),
            "CapacitorSectionId": row.get("SectionId"),
            "CapacitorRatedKvColumnUsed": rated_kv_column,
            "CapacitorRatedKvForCheck": capacitor_kv,
            "SectionVoltageColumnUsed": section_voltage_column,
            "SectionVoltageKvForCheck": voltage_context.get("SectionVoltageKvForCheck"),
            "SectionConfigurationColumnUsed": voltage_context.get("SectionConfigurationColumnUsed"),
            "SectionConfigurationRawValueForCheck": voltage_context.get("SectionConfigurationRawValueForCheck"),
            "ConfigurationVoltageRawMatch": voltage_context.get("ConfigurationVoltageRawMatch"),
            "ConfigurationVoltageLLKv": voltage_context.get("ConfigurationVoltageLLKv"),
            "ConfigurationVoltageLNKv": voltage_context.get("ConfigurationVoltageLNKv"),
            "ExpectedVoltageKvForCheck": expected_kv,
            "ExpectedVoltageSource": voltage_context.get("ExpectedVoltageSource"),
            "VoltagePercentDifference": percent_difference,
            "VR6DiagnosticStatus": diagnostic_status,
        }
        context_row.update(voltage_context)
        capacitor_voltage_context_rows.append(context_row)

        if diagnostic_status != "VR6 mismatch":
            continue

        temp = row.copy()
        temp["CapacitorRatedKvForCheck"] = capacitor_kv
        temp["ExpectedVoltageKvForCheck"] = expected_kv
        temp["VoltagePercentDifference"] = percent_difference
        temp["SectionVoltageColumnUsed"] = section_voltage_column
        temp["SectionConfigurationColumnUsed"] = voltage_context.get("SectionConfigurationColumnUsed")
        temp["SectionConfigurationRawValueForCheck"] = voltage_context.get("SectionConfigurationRawValueForCheck")

        for key, value in voltage_context.items():
            temp[key] = value

        for key, value in _build_capacitor_totals(row).items():
            temp[key] = value

        capacitor_voltage_issue_rows.append(temp)

    capacitor_voltage_issues = add_rule_columns(
        pd.DataFrame(capacitor_voltage_issue_rows),
        rule=get_rule("VR6"),
        element_type="Capacitor",
        element_id="UniqueDeviceId",
    )

    # Make the issue wording more specific now that transformer-aware logic exists.
    if not capacitor_voltage_issues.empty:
        capacitor_voltage_issues["Issue"] = "Capacitor voltage mismatch"
        capacitor_voltage_issues["Description"] = capacitor_voltage_issues.apply(
            lambda row: (
                f"Capacitor RatedKv {row.get('CapacitorRatedKvForCheck')} kV does not match "
                f"expected connected voltage {row.get('ExpectedVoltageKvForCheck')} kV. "
                f"Voltage source used: {row.get('ExpectedVoltageSource')}."
            ),
            axis=1,
        )
        capacitor_voltage_issues["RecommendedAction"] = (
            "Review capacitor RatedKv, connected SectionId, section voltage, and any upstream/downstream transformer voltage."
        )

    capacitor_issues = pd.concat(
        [
            capacitor_rating_issues,
            capacitor_missing_rated_kv_issues,
            capacitor_voltage_issues,
            phase_mismatches,
        ],
        ignore_index=True,
    )

    results["capacitor_issues"] = capacitor_issues
    results["transformer_locations"] = transformer_locations
    results["capacitor_voltage_context"] = pd.DataFrame(capacitor_voltage_context_rows)

    print("\n========================")
    print("CAPACITOR SUMMARY")
    print("========================")
    print("VR5 zero or missing kVAR rating:", len(capacitor_rating_issues))
    print("VR6 missing or zero RatedKv:", len(capacitor_missing_rated_kv_issues))
    print("VR6 voltage mismatch:", len(capacitor_voltage_issues))
    print("VR7 phase mismatch:", len(phase_mismatches))
    print(f"Total capacitor issues found: {len(capacitor_issues)}")

    return results
