"""Functionality related to the PEtab entity mapping table"""

# TODO: Move to petab.v2.mapping
from pathlib import Path

import pandas as pd

from . import lint
from .C import *  # noqa: F403
from .models import Model

__all__ = [
    "get_mapping_df",
    "write_mapping_df",
    "check_mapping_df",
    "resolve_mapping",
]


def get_mapping_df(
    mapping_file: None | str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """
    Read the provided mapping file into a ``pandas.Dataframe``.

    Arguments:
        mapping_file: Name of file to read from or pandas.Dataframe

    Returns:
        Mapping DataFrame
    """
    if mapping_file is None:
        return mapping_file

    if isinstance(mapping_file, str | Path):
        mapping_file = pd.read_csv(
            mapping_file, sep="\t", float_precision="round_trip"
        )

    if not isinstance(mapping_file.index, pd.RangeIndex):
        mapping_file.reset_index(
            drop=mapping_file.index.name != PETAB_ENTITY_ID,
            inplace=True,
        )

    for col in MAPPING_DF_REQUIRED_COLS:
        if col not in mapping_file.columns:
            raise KeyError(f"Mapping table missing mandatory field {col}.")

        lint.assert_no_leading_trailing_whitespace(
            mapping_file.reset_index()[col].values, col
        )

    mapping_file.set_index([PETAB_ENTITY_ID], inplace=True)

    return mapping_file


def write_mapping_df(df: pd.DataFrame, filename: str | Path) -> None:
    """Write PEtab mapping table

    Arguments:
        df: PEtab mapping table
        filename: Destination file name. The parent directory will be created
            if necessary.
    """
    df = get_mapping_df(df)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filename, sep="\t", index=True)


def check_mapping_df(
    df: pd.DataFrame,
    model: Model | None = None,
) -> None:
    """Run sanity checks on PEtab mapping table

    Arguments:
        df: PEtab mapping DataFrame
        model: Model for additional checking of parameter IDs

    Raises:
        AssertionError: in case of problems
    """
    lint._check_df(df, MAPPING_DF_REQUIRED_COLS[1:], "mapping")

    if df.index.name != PETAB_ENTITY_ID:
        raise AssertionError(
            f"Mapping table has wrong index {df.index.name}. "
            f"Expected {PETAB_ENTITY_ID}."
        )

    lint.check_ids(df.index.values, kind=PETAB_ENTITY_ID)

    if model:
        for model_entity_id in df[MODEL_ENTITY_ID]:
            if not model.has_entity_with_id(model_entity_id):
                raise AssertionError(
                    "Mapping table maps to unknown "
                    f"model entity ID {model_entity_id}."
                )


def resolve_mapping(mapping_df: pd.DataFrame | None, element: str) -> str:
    """Resolve mapping for a given element.

    :param element:
        Element to resolve.

    :param mapping_df:
        Mapping table.

    :return:
        Resolved element.
    """
    if mapping_df is None:
        return element
    if element in mapping_df.index:
        return mapping_df.loc[element, MODEL_ENTITY_ID]
    return element
