"""Functions performing various calculations."""

import numbers
import operator
from functools import reduce

import numpy as np
import pandas as pd
import sympy as sp

from petab.v1 import is_empty, split_parameter_replacement_list

from .C import *
from .math import sympify_petab

__all__ = [
    "calculate_residuals",
    "calculate_residuals_for_table",
    "get_symbolic_noise_formulas",
    "evaluate_noise_formula",
    "calculate_chi2",
    "calculate_chi2_for_table_from_residuals",
    "calculate_llh",
    "calculate_llh_for_table",
    "calculate_single_llh",
]


def calculate_residuals(
    measurement_dfs: list[pd.DataFrame] | pd.DataFrame,
    simulation_dfs: list[pd.DataFrame] | pd.DataFrame,
    observable_dfs: list[pd.DataFrame] | pd.DataFrame,
    parameter_dfs: list[pd.DataFrame] | pd.DataFrame,
    normalize: bool = True,
    scale: bool = True,
) -> list[pd.DataFrame]:
    """Calculate residuals.

    Arguments:
        measurement_dfs:
            The problem measurement tables.
        simulation_dfs:
            Simulation tables corresponding to the measurement tables.
        observable_dfs:
            The problem observable tables.
        parameter_dfs:
            The problem parameter tables.
        normalize:
            Whether to normalize residuals by the noise standard deviation
            terms.
        scale:
            Whether to calculate residuals of scaled values.

    Returns:
        List of DataFrames in the same structure as `measurement_dfs`
        with a field `residual` instead of measurement.
    """
    # convenience
    if isinstance(measurement_dfs, pd.DataFrame):
        measurement_dfs = [measurement_dfs]
    if isinstance(simulation_dfs, pd.DataFrame):
        simulation_dfs = [simulation_dfs]
    if isinstance(observable_dfs, pd.DataFrame):
        observable_dfs = [observable_dfs]
    if isinstance(parameter_dfs, pd.DataFrame):
        parameter_dfs = [parameter_dfs]

    # iterate over data frames
    residual_dfs = []
    for measurement_df, simulation_df, observable_df, parameter_df in zip(
        measurement_dfs,
        simulation_dfs,
        observable_dfs,
        parameter_dfs,
        strict=True,
    ):
        residual_df = calculate_residuals_for_table(
            measurement_df,
            simulation_df,
            observable_df,
            parameter_df,
            normalize,
            scale,
        )
        residual_dfs.append(residual_df)
    return residual_dfs


def calculate_residuals_for_table(
    measurement_df: pd.DataFrame,
    simulation_df: pd.DataFrame,
    observable_df: pd.DataFrame,
    parameter_df: pd.DataFrame,
    normalize: bool = True,
    scale: bool = True,
) -> pd.DataFrame:
    """
    Calculate residuals for a single measurement table.
    For the arguments, see `calculate_residuals`.
    """
    from petab.v1 import scale

    # below, we rely on a unique index
    measurement_df = measurement_df.reset_index(drop=True)

    # create residual df as copy of measurement df, change column
    residual_df = measurement_df.copy(deep=True).rename(
        columns={MEASUREMENT: RESIDUAL}
    )
    residual_df[RESIDUAL] = residual_df[RESIDUAL].astype("float64")
    # matching columns
    compared_cols = set(measurement_df.columns) & set(simulation_df.columns)

    # compute noise formulas for observables
    noise_formulas = get_symbolic_noise_formulas(observable_df)

    # iterate over measurements, find corresponding simulations
    for irow, row in measurement_df.iterrows():
        measurement = row[MEASUREMENT]
        # look up in simulation df
        masks = [
            (simulation_df[col] == row[col]) | is_empty(row[col])
            for col in compared_cols
        ]
        mask = reduce(operator.and_, masks)
        if mask.sum() == 0:
            raise ValueError(
                f"Could not find simulation for measurement {row}."
            )
        # if we have multiple matches, check that the rows are all identical
        elif (
            mask.sum() > 1
            and simulation_df.loc[mask].drop_duplicates().shape[0] > 1
        ):
            raise ValueError(
                f"Multiple different simulations found for measurement "
                f"{row}:\n{simulation_df.loc[mask]}"
            )

        simulation = simulation_df.loc[mask][SIMULATION].iloc[0]
        if scale:
            # apply scaling
            observable = observable_df.loc[row[OBSERVABLE_ID]]
            # for v2, the transformation is part of the noise distribution
            noise_distr = observable.get(NOISE_DISTRIBUTION, NORMAL)
            if noise_distr.startswith("log-"):
                trafo = LOG
            elif noise_distr.startswith("log10-"):
                trafo = LOG10
            else:
                trafo = LIN

            # scale simulation and measurement

            scaled_simulation = scale(simulation, trafo)
            scaled_measurement = scale(measurement, trafo)

        # non-normalized residual is just the difference
        residual = scaled_measurement - scaled_simulation

        if normalize:
            # divide by standard deviation
            residual /= evaluate_noise_formula(
                row, noise_formulas, parameter_df, simulation, observable
            )

        # fill in value
        residual_df.loc[irow, RESIDUAL] = residual
    return residual_df


def get_symbolic_noise_formulas(observable_df) -> dict[str, sp.Expr]:
    """Sympify noise formulas.

    Arguments:
        observable_df: The observable table.

    Returns:
        Dictionary of {observable_id}: {noise_formula}.
    """
    noise_formulas = {}
    # iterate over observables
    for observable_id, row in observable_df.iterrows():
        noise_formulas[observable_id] = (
            sympify_petab(row.noiseFormula) if NOISE_FORMULA in row else None
        )
    return noise_formulas


def evaluate_noise_formula(
    measurement: pd.Series,
    noise_formulas: dict[str, sp.Expr],
    parameter_df: pd.DataFrame,
    simulation: numbers.Number,
    observable: dict,
) -> float:
    """Fill in parameters for `measurement` and evaluate noise_formula.

    Arguments:
        measurement: A measurement table row.
        noise_formulas: The noise formulas as computed by
            `get_symbolic_noise_formulas`.
        parameter_df: The parameter table.
        simulation: The simulation corresponding to the measurement, scaled.
        observable: The observable table row corresponding to the measurement.

    Returns:
        The noise value.
    """
    # the observable id
    observable_id = measurement[OBSERVABLE_ID]

    # extract measurement specific overrides
    observable_parameter_overrides = split_parameter_replacement_list(
        measurement.get(OBSERVABLE_PARAMETERS, None)
    )
    noise_parameter_overrides = split_parameter_replacement_list(
        measurement.get(NOISE_PARAMETERS, None)
    )
    observable_parameter_placeholders = observable.get(
        OBSERVABLE_PLACEHOLDERS, ""
    ).split(PARAMETER_SEPARATOR)
    noise_parameter_placeholders = observable.get(
        NOISE_PLACEHOLDERS, ""
    ).split(PARAMETER_SEPARATOR)

    # fill in measurement specific parameters
    overrides = {
        sp.Symbol(placeholder, real=True): override
        for placeholder, override in zip(
            [
                p.strip()
                for p in observable_parameter_placeholders
                + noise_parameter_placeholders
                if p.strip()
            ],
            observable_parameter_overrides + noise_parameter_overrides,
            strict=False,
        )
    }

    # fill in observables
    overrides[sp.Symbol(observable_id, real=True)] = simulation

    # fill in general parameters
    for row in parameter_df.itertuples():
        overrides[sp.Symbol(row.Index, real=True)] = row.nominalValue

    # replace parametric measurement specific parameters
    for key, value in overrides.items():
        if not isinstance(value, numbers.Number):
            # is parameter
            overrides[key] = parameter_df.loc[value, NOMINAL_VALUE]

    # replace parameters by values in formula
    noise_formula = noise_formulas[observable_id]
    noise_value = noise_formula.subs(overrides)

    # conversion is possible if all parameters are replaced
    try:
        noise_value = float(noise_value)
    except TypeError as e:
        raise ValueError(
            f"Cannot replace all parameters in noise formula {noise_value} "
            f"for observable {observable_id}. "
            f"Missing {noise_formula.free_symbols}. Note that model states "
            "are currently not supported."
        ) from e
    return noise_value


def calculate_chi2(
    measurement_dfs: list[pd.DataFrame] | pd.DataFrame,
    simulation_dfs: list[pd.DataFrame] | pd.DataFrame,
    observable_dfs: list[pd.DataFrame] | pd.DataFrame,
    parameter_dfs: list[pd.DataFrame] | pd.DataFrame,
    normalize: bool = True,
    scale: bool = True,
) -> float:
    """Calculate the chi2 value.

    Arguments:
        measurement_dfs:
            The problem measurement tables.
        simulation_dfs:
            Simulation tables corresponding to the measurement tables.
        observable_dfs:
            The problem observable tables.
        parameter_dfs:
            The problem parameter tables.
        normalize:
            Whether to normalize residuals by the noise standard deviation
            terms.
        scale:
            Whether to calculate residuals of scaled values.

    Returns:
        The aggregated chi2 value.
    """
    residual_dfs = calculate_residuals(
        measurement_dfs,
        simulation_dfs,
        observable_dfs,
        parameter_dfs,
        normalize,
        scale,
    )
    chi2s = [
        calculate_chi2_for_table_from_residuals(df) for df in residual_dfs
    ]
    return sum(chi2s)


def calculate_chi2_for_table_from_residuals(
    residual_df: pd.DataFrame,
) -> float:
    """Compute chi2 value for a single residual table."""
    return (np.array(residual_df[RESIDUAL]) ** 2).sum()


def calculate_llh(
    measurement_dfs: list[pd.DataFrame] | pd.DataFrame,
    simulation_dfs: list[pd.DataFrame] | pd.DataFrame,
    observable_dfs: list[pd.DataFrame] | pd.DataFrame,
    parameter_dfs: list[pd.DataFrame] | pd.DataFrame,
) -> float:
    """Calculate total log likelihood.

    Arguments:
        measurement_dfs:
            The problem measurement tables.
        simulation_dfs:
            Simulation tables corresponding to the measurement tables.
        observable_dfs:
            The problem observable tables.
        parameter_dfs:
            The problem parameter tables.

    Returns:
        The log-likelihood.
    """
    # convenience
    if isinstance(measurement_dfs, pd.DataFrame):
        measurement_dfs = [measurement_dfs]
    if isinstance(simulation_dfs, pd.DataFrame):
        simulation_dfs = [simulation_dfs]
    if isinstance(observable_dfs, pd.DataFrame):
        observable_dfs = [observable_dfs]
    if isinstance(parameter_dfs, pd.DataFrame):
        parameter_dfs = [parameter_dfs]

    # iterate over data frames
    llhs = []
    for measurement_df, simulation_df, observable_df, parameter_df in zip(
        measurement_dfs,
        simulation_dfs,
        observable_dfs,
        parameter_dfs,
        strict=True,
    ):
        _llh = calculate_llh_for_table(
            measurement_df, simulation_df, observable_df, parameter_df
        )
        llhs.append(_llh)
    return sum(llhs)


def calculate_llh_for_table(
    measurement_df: pd.DataFrame,
    simulation_df: pd.DataFrame,
    observable_df: pd.DataFrame,
    parameter_df: pd.DataFrame,
) -> float:
    """Calculate log-likelihood for one set of tables. For the arguments, see
    `calculate_llh`.
    """

    llhs = []

    # matching columns
    compared_cols = set(measurement_df.columns) & set(simulation_df.columns)

    # compute noise formulas for observables
    noise_formulas = get_symbolic_noise_formulas(observable_df)

    # iterate over measurements, find corresponding simulations
    for _, row in measurement_df.iterrows():
        measurement = row[MEASUREMENT]

        # look up in simulation df
        masks = [
            (simulation_df[col] == row[col]) | is_empty(row[col])
            for col in compared_cols
        ]
        mask = reduce(lambda x, y: x & y, masks)

        simulation = simulation_df.loc[mask][SIMULATION].iloc[0]

        observable = observable_df.loc[row[OBSERVABLE_ID]]

        # get noise distribution
        noise_distr = observable.get(NOISE_DISTRIBUTION, NORMAL)

        if noise_distr.startswith("log-"):
            obs_scale = LOG
            noise_distr = noise_distr.removeprefix("log-")
        elif noise_distr.startswith("log10-"):
            obs_scale = LOG10
            noise_distr = noise_distr.removeprefix("log10-")
        else:
            obs_scale = LIN

        # get noise standard deviation
        noise_value = evaluate_noise_formula(
            row,
            noise_formulas,
            parameter_df,
            simulation,
            observable,
        )

        llh = calculate_single_llh(
            measurement, simulation, obs_scale, noise_distr, noise_value
        )
        llhs.append(llh)
    return sum(llhs)


def calculate_single_llh(
    measurement: float,
    simulation: float,
    scale: str,
    noise_distribution: str,
    noise_value: float,
) -> float:
    """Calculate a single log likelihood.

    Arguments:
        measurement: The measurement value.
        simulation: The simulated value.
        scale: The scale on which the noise model is to be applied.
        noise_distribution: The noise distribution.
        noise_value: The considered noise models possess a single noise
            parameter, e.g. the normal standard deviation.

    Returns:
        The computed likelihood for the given values.
    """
    # PEtab v2:
    if noise_distribution == LOG10_NORMAL and scale == LIN:
        noise_distribution = NORMAL
        scale = LOG10
    elif noise_distribution == LOG_NORMAL and scale == LIN:
        noise_distribution = NORMAL
        scale = LOG

    # short-hand
    m, s, sigma = measurement, simulation, noise_value
    pi, log, log10 = np.pi, np.log, np.log10

    # go over the possible cases
    if noise_distribution == NORMAL and scale == LIN:
        nllh = 0.5 * log(2 * pi * sigma**2) + 0.5 * ((s - m) / sigma) ** 2
    elif noise_distribution == NORMAL and scale == LOG:
        nllh = (
            0.5 * log(2 * pi * sigma**2 * m**2)
            + 0.5 * ((log(s) - log(m)) / sigma) ** 2
        )
    elif noise_distribution == NORMAL and scale == LOG10:
        nllh = (
            0.5 * log(2 * pi * sigma**2 * m**2 * log(10) ** 2)
            + 0.5 * ((log10(s) - log10(m)) / sigma) ** 2
        )
    elif noise_distribution == LAPLACE and scale == LIN:
        nllh = log(2 * sigma) + abs((s - m) / sigma)
    elif noise_distribution == LAPLACE and scale == LOG:
        nllh = log(2 * sigma * m) + abs((log(s) - log(m)) / sigma)
    elif noise_distribution == LAPLACE and scale == LOG10:
        nllh = log(2 * sigma * m * log(10)) + abs(
            (log10(s) - log10(m)) / sigma
        )
    else:
        raise NotImplementedError(
            "Unsupported combination of noise_distribution and scale "
            f"specified: {noise_distribution}, {scale}."
        )
    return -nllh
