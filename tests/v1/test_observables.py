"""Tests for petab.observables"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

import petab
from petab.C import *

# import fixtures
pytest_plugins = [
    "tests.v1.test_petab",
]


def test_get_observable_df():
    """Test measurements.get_measurement_df."""
    # without id
    observable_df = pd.DataFrame(
        data={
            OBSERVABLE_NAME: ["observable name 1"],
            OBSERVABLE_FORMULA: ["observable_1"],
            NOISE_FORMULA: [1],
        }
    )

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as fh:
        file_name = fh.name
        observable_df.to_csv(fh, sep="\t", index=False)

    with pytest.raises(KeyError):
        petab.get_observable_df(file_name)

    # with id
    observable_df[OBSERVABLE_ID] = ["observable_1"]

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as fh:
        file_name = fh.name
        observable_df.to_csv(fh, sep="\t", index=False)

    df = petab.get_observable_df(file_name)
    assert (df == observable_df.set_index(OBSERVABLE_ID)).all().all()

    # test other arguments
    assert (
        (petab.get_observable_df(observable_df) == observable_df).all().all()
    )
    assert petab.get_observable_df(None) is None


def test_write_observable_df():
    """Test measurements.get_measurement_df."""
    observable_df = pd.DataFrame(
        data={
            OBSERVABLE_ID: ["observable_1"],
            OBSERVABLE_NAME: ["observable name 1"],
            OBSERVABLE_FORMULA: ["observable_1"],
            NOISE_FORMULA: [1],
        }
    ).set_index(OBSERVABLE_ID)

    with tempfile.TemporaryDirectory() as temp_dir:
        file_name = Path(temp_dir) / "observables.tsv"
        petab.write_observable_df(observable_df, file_name)
        re_df = petab.get_observable_df(file_name)
        assert (observable_df == re_df).all().all()


def test_get_output_parameters():
    """Test measurements.get_output_parameters."""
    from petab.models.sbml_model import SbmlModel

    model = SbmlModel.from_antimony(
        "fixedParameter1 = 1.0; observable_1 = 1.0"
    )

    # observable file
    observable_df = pd.DataFrame(
        data={
            OBSERVABLE_ID: ["observable_1"],
            OBSERVABLE_NAME: ["observable name 1"],
            OBSERVABLE_FORMULA: ["observable_1 * scaling + offset"],
            NOISE_FORMULA: [1],
        }
    ).set_index(OBSERVABLE_ID)

    output_parameters = petab.get_output_parameters(observable_df, model)

    assert output_parameters == ["offset", "scaling"]

    # test sympy-special symbols (e.g. N, beta, ...)
    # see https://github.com/ICB-DCM/pyPESTO/issues/1048
    observable_df = pd.DataFrame(
        data={
            OBSERVABLE_ID: ["observable_1"],
            OBSERVABLE_NAME: ["observable name 1"],
            OBSERVABLE_FORMULA: ["observable_1 * N + beta"],
            NOISE_FORMULA: [1],
        }
    ).set_index(OBSERVABLE_ID)

    output_parameters = petab.get_output_parameters(observable_df, model)

    assert output_parameters == ["N", "beta"]


def test_get_formula_placeholders():
    """Test get_formula_placeholders"""
    # no placeholder
    assert petab.get_formula_placeholders("1.0", "any", "observable") == []

    # multiple placeholders
    assert petab.get_formula_placeholders(
        "observableParameter1_twoParams * "
        "observableParameter2_twoParams + otherParam",
        "twoParams",
        "observable",
    ) == ["observableParameter1_twoParams", "observableParameter2_twoParams"]

    # noise placeholder
    assert petab.get_formula_placeholders(
        "3.0 * noiseParameter1_oneParam", "oneParam", "noise"
    ) == ["noiseParameter1_oneParam"]

    # multiple instances and in 'wrong' order
    assert petab.get_formula_placeholders(
        "observableParameter2_twoParams * "
        "observableParameter1_twoParams + "
        "otherParam / observableParameter2_twoParams",
        "twoParams",
        "observable",
    ) == ["observableParameter1_twoParams", "observableParameter2_twoParams"]

    # non-consecutive numbering
    with pytest.raises(AssertionError):
        petab.get_formula_placeholders(
            "observableParameter2_twoParams + observableParameter2_twoParams",
            "twoParams",
            "observable",
        )

    # empty
    assert petab.get_formula_placeholders("", "any", "observable") == []

    # non-string
    assert petab.get_formula_placeholders(1, "any", "observable") == []


def test_create_observable_df():
    """Test observables.create_measurement_df."""
    df = petab.create_observable_df()
    assert set(df.columns.values) == set(OBSERVABLE_DF_COLS)


def test_get_placeholders():
    """Test get_placeholders"""
    observable_df = pd.DataFrame(
        data={
            OBSERVABLE_ID: ["obs_1", "obs_2"],
            OBSERVABLE_FORMULA: [
                "observableParameter1_obs_1 * 2 * foo",
                "1 + observableParameter1_obs_2",
            ],
        }
    ).set_index(OBSERVABLE_ID)

    # test with missing noiseFormula
    expected = ["observableParameter1_obs_1", "observableParameter1_obs_2"]
    actual = petab.get_placeholders(observable_df)
    assert actual == expected

    # test with noiseFormula
    observable_df[NOISE_FORMULA] = ["noiseParameter1_obs_1", "2.0"]
    expected = [
        "observableParameter1_obs_1",
        "noiseParameter1_obs_1",
        "observableParameter1_obs_2",
    ]
    actual = petab.get_placeholders(observable_df)
    assert actual == expected
