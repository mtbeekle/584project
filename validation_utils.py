import pandas as pd


TRUE_VALUES = {
    True,
    1,
    -1,
    "1",
    "-1",
    "true",
    "t",
    "yes",
    "y",
    "open",
    "on",
}

FALSE_VALUES = {
    False,
    0,
    "0",
    "false",
    "f",
    "no",
    "n",
    "closed",
    "off",
}


def validate_required_columns(
    dataframe: pd.DataFrame,
    dataframe_name: str,
    required_columns: list[str],
) -> None:
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        missing_list = ", ".join(missing_columns)
        raise ValueError(
            f"{dataframe_name} is missing required column(s): {missing_list}"
        )


def normalize_boolean_value(value) -> bool | None:
    if pd.isna(value):
        return None

    if isinstance(value, str):
        normalized_value = value.strip().lower()
    else:
        normalized_value = value

    if normalized_value in TRUE_VALUES:
        return True

    if normalized_value in FALSE_VALUES:
        return False

    return None


def is_true_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_boolean_value).eq(True)


def is_false_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_boolean_value).eq(False)


def add_issue_columns(
    dataframe: pd.DataFrame,
    rule_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    issue: str | None = None,
    description: str | None = None,
    recommended_action: str | None = None,
) -> pd.DataFrame:
    issue_dataframe = dataframe.copy()

    if rule_id is not None:
        issue_dataframe["RuleID"] = rule_id
    if category is not None:
        issue_dataframe["Category"] = category
    if severity is not None:
        issue_dataframe["Severity"] = severity
    if issue is not None:
        issue_dataframe["Issue"] = issue
    if description is not None:
        issue_dataframe["Description"] = description
    if recommended_action is not None:
        issue_dataframe["RecommendedAction"] = recommended_action

    return issue_dataframe
