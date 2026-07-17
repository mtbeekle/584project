import pandas as pd

from rules import get_rule
from validation_utils import add_rule_columns, clean_column_names


SOURCE_ID_COLUMNS = [
    "SourceId",
    "SourceID",
    "FeederId",
    "FeederID",
    "SubstationId",
    "SubstationID",
    "Name",
    "Id",
    "ID",
]

SOURCE_VOLTAGE_COLUMNS = [
    "SourceNominalKv",
    "SourceNominalKV",
    "NominalKvll",
    "NominalKVLL",
    "NominalKv",
    "NominalKV",
    "BaseKv",
    "BaseKV",
]

EXPECTED_VOLTAGE_COLUMNS = [
    "BusVoltageLevel",
    "FeederVoltage",
    "FeederNominalKv",
    "FeederNominalKV",
    "SystemVoltage",
    "SystemNominalKv",
    "SystemNominalKV",
]

BY_PHASE_VOLTAGE_COLUMNS = [
    "ByPhVoltLevelPh1",
    "ByPhVoltLevelPh2",
    "ByPhVoltLevelPh3",
]

VR3_VOLTAGE_TOLERANCE_PCT = 10.0
MIN_FEEDER_KV = 1.0
MAX_FEEDER_KV = 100.0


def _empty_results() -> dict[str, pd.DataFrame]:
    return {
        "source_voltage_issues": pd.DataFrame(),
        "source_voltage_context": pd.DataFrame(),
    }


def _key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "")


def _find_col(dataframe: pd.DataFrame | None, names: list[str]) -> str | None:
    if dataframe is None or dataframe.empty:
        return None

    lookup = {_key(column): column for column in dataframe.columns}
    for name in names:
        matched = lookup.get(_key(name))
        if matched:
            return matched
    return None


def _voltage_kv(value: object) -> float:
    if value is None:
        return float("nan")

    try:
        if pd.isna(value):
            return float("nan")
    except Exception:
        pass

    text = str(value).strip().replace(",", "")
    if not text:
        return float("nan")

    for unit in ["kV", "KV", "kv", "V"]:
        text = text.replace(unit, "")

    try:
        numeric_value = float(text.strip())
    except Exception:
        return float("nan")

    return numeric_value / 1000.0 if abs(numeric_value) > 1000 else numeric_value


def _valid_kv(value: object) -> bool:
    try:
        return not pd.isna(value) and float(value) > 0
    except Exception:
        return False


def _plausible_feeder_kv(value: object) -> bool:
    if not _valid_kv(value):
        return False
    return MIN_FEEDER_KV <= float(value) <= MAX_FEEDER_KV


def _by_phase_expected_voltage(row: pd.Series) -> tuple[float, str | None]:
    available_values = []
    for column in BY_PHASE_VOLTAGE_COLUMNS:
        if column not in row.index:
            continue
        kv = _voltage_kv(row[column])
        if _plausible_feeder_kv(kv):
            available_values.append(kv)

    if not available_values:
        return float("nan"), None

    return max(available_values), "maximum by-phase voltage level"


def _expected_voltage(row: pd.Series, expected_voltage_col: str | None) -> tuple[float, str | None]:
    if expected_voltage_col:
        kv = _voltage_kv(row[expected_voltage_col])
        if _plausible_feeder_kv(kv):
            return kv, expected_voltage_col

    return _by_phase_expected_voltage(row)


def check_source_voltage(sources: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    """
    VR3 - source voltage mismatch.

    Compares a source/feed nominal voltage against an expected feeder/system
    voltage when both values are available. Rows without enough voltage evidence
    are recorded in the diagnostic context but are not reported as issues.
    """
    sources = clean_column_names(sources)
    if sources.empty:
        return _empty_results()

    source_id_col = _find_col(sources, SOURCE_ID_COLUMNS)
    source_voltage_col = _find_col(sources, SOURCE_VOLTAGE_COLUMNS)
    expected_voltage_col = _find_col(sources, EXPECTED_VOLTAGE_COLUMNS)

    issue_rows = []
    context_rows = []

    for _, row in sources.iterrows():
        source_id = row[source_id_col] if source_id_col else None
        source_kv = _voltage_kv(row[source_voltage_col]) if source_voltage_col else float("nan")
        expected_kv, expected_source = _expected_voltage(row, expected_voltage_col)

        if not source_voltage_col:
            status = "Cannot run VR3: source nominal voltage column not found"
            percent_difference = float("nan")
        elif not _valid_kv(source_kv):
            status = "Cannot run VR3: source nominal voltage is missing, zero, or unreadable"
            percent_difference = float("nan")
        elif not _valid_kv(expected_kv):
            status = "Cannot run VR3: expected feeder/system voltage is missing, zero, or unreadable"
            percent_difference = float("nan")
        else:
            percent_difference = abs(source_kv - expected_kv) / expected_kv * 100
            status = (
                "VR3 source voltage mismatch"
                if percent_difference > VR3_VOLTAGE_TOLERANCE_PCT
                else "VR3 voltage pass"
            )

        context = {
            "SourceIdForCheck": source_id,
            "SourceVoltageColumnUsed": source_voltage_col,
            "SourceVoltageKvForCheck": source_kv,
            "ExpectedVoltageColumnUsed": expected_source,
            "ExpectedVoltageKvForCheck": expected_kv,
            "VoltagePercentDifference": percent_difference,
            "VR3VoltageStatus": status,
        }
        context_rows.append(context)

        if status != "VR3 source voltage mismatch":
            continue

        temp = row.copy()
        for key, value in context.items():
            temp[key] = value
        issue_rows.append(temp)

    source_voltage_issues = add_rule_columns(
        pd.DataFrame(issue_rows),
        rule=get_rule("VR3"),
        element_type="Source",
        element_id="SourceIdForCheck",
    )
    if not source_voltage_issues.empty:
        source_voltage_issues["Description"] = source_voltage_issues.apply(
            lambda row: (
                f"Source voltage {row.get('SourceVoltageKvForCheck')} kV does not match "
                f"expected feeder/system voltage {row.get('ExpectedVoltageKvForCheck')} kV."
            ),
            axis=1,
        )
        source_voltage_issues["RecommendedAction"] = (
            "Review source nominal voltage, feeder/system nominal voltage, and connected section ratings."
        )

    print("\n========================")
    print("SOURCE VOLTAGE SUMMARY")
    print("========================")
    print("Source voltage rows checked:", len(sources))
    print("VR3 source voltage mismatch:", len(source_voltage_issues))

    return {
        "source_voltage_issues": source_voltage_issues,
        "source_voltage_context": pd.DataFrame(context_rows),
    }
