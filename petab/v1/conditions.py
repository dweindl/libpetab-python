"""Functions operating on the PEtab condition table"""

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from . import core, lint
from .C import *

__all__ = [
    "get_condition_df",
    "write_condition_df",
    "create_condition_df",
    "get_parametric_overrides",
]


def get_condition_df(
    condition_file: str | pd.DataFrame | Path | None,
) -> pd.DataFrame:
    """Read the provided condition file into a ``pandas.Dataframe``

    Conditions are rows, parameters are columns, conditionId is index.

    Arguments:
        condition_file: File name of PEtab condition file or pandas.Dataframe
    """
    if condition_file is None:
        return condition_file

    if isinstance(condition_file, str | Path):
        condition_file = pd.read_csv(
            condition_file, sep="\t", float_precision="round_trip"
        )

    lint.assert_no_leading_trailing_whitespace(
        condition_file.columns.values, "condition"
    )

    if not isinstance(condition_file.index, pd.RangeIndex):
        condition_file.reset_index(
            drop=condition_file.index.name != CONDITION_ID,
            inplace=True,
        )

    try:
        condition_file.set_index([CONDITION_ID], inplace=True)
    except KeyError:
        raise KeyError(
            f"Condition table missing mandatory field {CONDITION_ID}."
        ) from None

    return condition_file


def write_condition_df(df: pd.DataFrame, filename: str | Path) -> None:
    """Write PEtab condition table

    Arguments:
        df: PEtab condition table
        filename: Destination file name. The parent directory will be created
            if necessary.
    """
    df = get_condition_df(df)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filename, sep="\t", index=True)


def create_condition_df(
    parameter_ids: Iterable[str], condition_ids: Iterable[str] | None = None
) -> pd.DataFrame:
    """Create empty condition DataFrame

    Arguments:
        parameter_ids: the columns
        condition_ids: the rows
    Returns:
        A :py:class:`pandas.DataFrame` with empty given rows and columns and
        all nan values
    """
    condition_ids = [] if condition_ids is None else list(condition_ids)

    data = {CONDITION_ID: condition_ids}
    df = pd.DataFrame(data)

    for p in parameter_ids:
        if not lint.is_valid_identifier(p):
            raise ValueError("Invalid parameter ID: " + p)
        df[p] = np.nan

    df.set_index(CONDITION_ID, inplace=True)

    return df


def get_parametric_overrides(condition_df: pd.DataFrame) -> list[str]:
    """Get parametric overrides from condition table

    Arguments:
        condition_df: PEtab condition table

    Returns:
        List of parameter IDs that are mapped in a condition-specific way
    """
    constant_parameters = set(condition_df.columns.values.tolist()) - {
        CONDITION_ID,
        CONDITION_NAME,
    }
    result = []

    for column in constant_parameters:
        if np.issubdtype(condition_df[column].dtype, np.number):
            continue

        floatified = condition_df.loc[:, column].apply(core.to_float_if_float)

        result.extend(x for x in floatified if not isinstance(x, float))
    return result
