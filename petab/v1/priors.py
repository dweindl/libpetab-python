"""Functions related to prior handling."""

from __future__ import annotations

import copy
from typing import Literal

import numpy as np
import pandas as pd

from ..v1.C import PREEQUILIBRATION_CONDITION_ID
from . import (
    ESTIMATE,
    LAPLACE,
    LIN,
    LOG,
    LOG10,
    LOG_LAPLACE,
    LOG_NORMAL,
    MEASUREMENT,
    NOISE_DISTRIBUTION,
    NOISE_FORMULA,
    NOISE_PARAMETERS,
    NORMAL,
    OBJECTIVE_PRIOR_PARAMETERS,
    OBJECTIVE_PRIOR_TYPE,
    OBSERVABLE_FORMULA,
    OBSERVABLE_ID,
    OBSERVABLE_TRANSFORMATION,
    PARAMETER_SCALE,
    PARAMETER_SCALE_LAPLACE,
    PARAMETER_SCALE_NORMAL,
    PARAMETER_SEPARATOR,
    SIMULATION_CONDITION_ID,
    TIME,
    C,
    Problem,
)
from .distributions import *
from .parameters import scale, unscale

__all__ = ["priors_to_measurements"]


class Prior:
    """A PEtab parameter prior.

    Different from the general :class:`Distribution`, this class is used to
    represent the prior distribution of a PEtab parameter using the
    PEtab-specific options like `parameterScale`, `*PriorType`,
    `*PriorParameters`, and `lowerBound` / `upperBounds`.

    :param type_: The type of the distribution.
    :param transformation: The transformation to be applied to the sample.
        Ignored if `parameter_scale` is `True`.
    :param parameters: The parameters of the distribution (unaffected by
        `parameter_scale` and `transformation`, but in the case of
        `parameterScale*` distribution types, the parameters are assumed to be
        on the `parameter_scale` scale).
    :param bounds: The untransformed bounds of the sample (lower, upper).
    :param transformation: The transformation of the distribution.
    """

    def __init__(
        self,
        type_: str,
        parameters: tuple,
        bounds: tuple = None,
        transformation: str = C.LIN,
    ):
        if transformation not in C.PARAMETER_SCALES:
            raise ValueError(
                f"Unknown parameter transformation: {transformation}"
            )

        if len(parameters) != 2:
            raise ValueError(
                f"Expected two parameters, got {len(parameters)}: {parameters}"
            )

        if bounds is not None and len(bounds) != 2:
            raise ValueError(
                "Expected (lowerBound, upperBound), got "
                f"{len(bounds)}: {bounds}"
            )

        self._type = type_
        self._parameters = parameters
        self._bounds = bounds
        self._transformation = transformation

        # create the underlying distribution
        match type_, transformation:
            case (C.UNIFORM, _) | (C.PARAMETER_SCALE_UNIFORM, C.LIN):
                self.distribution = Uniform(*parameters)
            case (C.NORMAL, _) | (C.PARAMETER_SCALE_NORMAL, C.LIN):
                self.distribution = Normal(*parameters)
            case (C.LAPLACE, _) | (C.PARAMETER_SCALE_LAPLACE, C.LIN):
                self.distribution = Laplace(*parameters)
            case (C.PARAMETER_SCALE_UNIFORM, C.LOG):
                self.distribution = Uniform(*parameters, log=True)
            case (C.LOG_NORMAL, _) | (C.PARAMETER_SCALE_NORMAL, C.LOG):
                self.distribution = Normal(*parameters, log=True)
            case (C.LOG_LAPLACE, _) | (C.PARAMETER_SCALE_LAPLACE, C.LOG):
                self.distribution = Laplace(*parameters, log=True)
            case (C.PARAMETER_SCALE_UNIFORM, C.LOG10):
                self.distribution = Uniform(*parameters, log=10)
            case (C.PARAMETER_SCALE_NORMAL, C.LOG10):
                self.distribution = Normal(*parameters, log=10)
            case (C.PARAMETER_SCALE_LAPLACE, C.LOG10):
                self.distribution = Laplace(*parameters, log=10)
            case _:
                raise ValueError(
                    "Unsupported distribution type / transformation: "
                    f"{type_} / {transformation}"
                )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{self.type!r}, {self.parameters!r},"
            f" bounds={self.bounds!r}, transformation={self.transformation!r},"
            ")"
        )

    @property
    def type(self):
        return self._type

    @property
    def parameters(self):
        return self._parameters

    @property
    def bounds(self):
        return self._bounds

    @property
    def transformation(self):
        return self._transformation

    def sample(self, shape=None) -> np.ndarray:
        """Sample from the distribution.

        :param shape: The shape of the sample.
        :return: A sample from the distribution.
        """
        raw_sample = self.distribution.sample(shape)
        return self._clip_to_bounds(self._scale_sample(raw_sample))

    def _scale_sample(self, sample):
        """Scale the sample to the parameter space"""
        # if self.on_parameter_scale:
        #     return sample

        return scale(sample, self.transformation)

    def _clip_to_bounds(self, x):
        """Clip `x` values to bounds.

        :param x: The values to clip. Assumed to be on the parameter scale.
        """
        # TODO: replace this by proper truncation
        if self.bounds is None:
            return x

        return np.maximum(
            np.minimum(self.ub_scaled, x),
            self.lb_scaled,
        )

    @property
    def lb_scaled(self):
        """The lower bound on the parameter scale."""
        return scale(self.bounds[0], self.transformation)

    @property
    def ub_scaled(self):
        """The upper bound on the parameter scale."""
        return scale(self.bounds[1], self.transformation)

    def pdf(self, x):
        """Probability density function at x.

        :param x: The value at which to evaluate the PDF.
            ``x`` is assumed to be on the parameter scale.
        :return: The value of the PDF at ``x``. Note that the PDF does
            currently not account for the clipping at the bounds.
        """
        x = unscale(x, self.transformation)

        # scale the PDF to the parameter scale
        if self.transformation == C.LIN:
            coeff = 1
        elif self.transformation == C.LOG10:
            coeff = x * np.log(10)
        elif self.transformation == C.LOG:
            coeff = x
        else:
            raise ValueError(f"Unknown transformation: {self.transformation}")

        return self.distribution.pdf(x) * coeff

    def neglogprior(self, x):
        """Negative log-prior at x.

        :param x: The value at which to evaluate the negative log-prior.
            ``x`` is assumed to be on the parameter scale.
        :return: The negative log-prior at ``x``.
        """
        return -np.log(self.pdf(x))

    @staticmethod
    def from_par_dict(
        d, type_=Literal["initialization", "objective"]
    ) -> Prior:
        """Create a distribution from a row of the parameter table.

        :param d: A dictionary representing a row of the parameter table.
        :param type_: The type of the distribution.
        :return: A distribution object.
        """
        dist_type = d.get(f"{type_}PriorType", C.PARAMETER_SCALE_UNIFORM)
        if not isinstance(dist_type, str) and np.isnan(dist_type):
            dist_type = C.PARAMETER_SCALE_UNIFORM

        pscale = d.get(C.PARAMETER_SCALE, C.LIN)
        params = d.get(f"{type_}PriorParameters", None)
        if pd.isna(params) and dist_type == C.PARAMETER_SCALE_UNIFORM:
            params = (
                scale(d[C.LOWER_BOUND], pscale),
                scale(d[C.UPPER_BOUND], pscale),
            )
        else:
            params = tuple(
                map(
                    float,
                    params.split(C.PARAMETER_SEPARATOR),
                )
            )
        return Prior(
            type_=dist_type,
            parameters=params,
            bounds=(d[C.LOWER_BOUND], d[C.UPPER_BOUND]),
            transformation=pscale,
        )


def priors_to_measurements(problem: Problem):
    """Convert priors to measurements.

    Reformulate the given problem such that the objective priors are converted
    to measurements. This is done by adding a new observable
    ``prior_{parameter_id}`` for each estimated parameter that has an objective
    prior, and adding a corresponding measurement to the measurement table.
    The new measurement is the prior distribution itself. The resulting
    optimization problem will be equivalent to the original problem.
    This is meant to be used for tools that do not support priors.

    The conversion involves the probability density function (PDF) of the
    prior, the parameters (e.g., location and scale) of that prior PDF, and the
    scale and value of the estimated parameter. Currently, `uniform` priors are
    not supported by this method. This method creates observables with:

    - `observableFormula`: the parameter value on the `parameterScale`
    - `observableTransformation`: `log` for `logNormal`/`logLaplace`
      distributions, `lin` otherwise

    and measurements with:

    - `measurement`: the PDF location
    - `noiseFormula`: the PDF scale

    Arguments
    ---------
    problem:
        The problem to be converted.

    Returns
    -------
    The new problem with the priors converted to measurements.
    """
    new_problem = copy.deepcopy(problem)

    # we only need to consider parameters that are estimated
    par_df_tmp = problem.parameter_df.loc[problem.parameter_df[ESTIMATE] == 1]

    if (
        OBJECTIVE_PRIOR_TYPE not in par_df_tmp
        or par_df_tmp.get(OBJECTIVE_PRIOR_TYPE).isna().all()
        or OBJECTIVE_PRIOR_PARAMETERS not in par_df_tmp
        or par_df_tmp.get(OBJECTIVE_PRIOR_PARAMETERS).isna().all()
    ):
        # nothing to do
        return new_problem

    def scaled_observable_formula(parameter_id, parameter_scale):
        if parameter_scale == LIN:
            return parameter_id
        if parameter_scale == LOG:
            return f"ln({parameter_id})"
        if parameter_scale == LOG10:
            return f"log10({parameter_id})"
        raise ValueError(f"Unknown parameter scale {parameter_scale}.")

    new_measurement_dicts = []
    new_observable_dicts = []
    for _, row in par_df_tmp.iterrows():
        prior_type = row[OBJECTIVE_PRIOR_TYPE]
        parameter_scale = row.get(PARAMETER_SCALE, LIN)
        if pd.isna(prior_type):
            if not pd.isna(row[OBJECTIVE_PRIOR_PARAMETERS]):
                raise AssertionError(
                    "Objective prior parameters are set, but prior type is "
                    "not specified."
                )
            continue

        if "uniform" in prior_type.lower():
            # for measurements, "uniform" is not supported yet
            #  if necessary, this could still be implemented by adding another
            #  observable/measurement that will produce a constant objective
            #  offset
            raise NotImplementedError("Uniform priors are not supported.")

        parameter_id = row.name
        prior_parameters = tuple(
            map(
                float,
                row[OBJECTIVE_PRIOR_PARAMETERS].split(PARAMETER_SEPARATOR),
            )
        )
        if len(prior_parameters) != 2:
            raise AssertionError(
                "Expected two objective prior parameters for parameter "
                f"{parameter_id}, but got {prior_parameters}."
            )

        # create new observable
        new_obs_id = f"prior_{parameter_id}"
        if new_obs_id in new_problem.observable_df.index:
            raise ValueError(
                f"Observable ID {new_obs_id}, which is to be "
                "created, already exists."
            )
        new_observable = {
            OBSERVABLE_ID: new_obs_id,
            OBSERVABLE_FORMULA: scaled_observable_formula(
                parameter_id,
                parameter_scale if "parameterScale" in prior_type else LIN,
            ),
            NOISE_FORMULA: f"noiseParameter1_{new_obs_id}",
        }
        if prior_type in (LOG_NORMAL, LOG_LAPLACE):
            new_observable[OBSERVABLE_TRANSFORMATION] = LOG
        elif OBSERVABLE_TRANSFORMATION in new_problem.observable_df:
            # only set default if the column is already present
            new_observable[OBSERVABLE_TRANSFORMATION] = LIN

        if prior_type in (NORMAL, PARAMETER_SCALE_NORMAL, LOG_NORMAL):
            new_observable[NOISE_DISTRIBUTION] = NORMAL
        elif prior_type in (LAPLACE, PARAMETER_SCALE_LAPLACE, LOG_LAPLACE):
            new_observable[NOISE_DISTRIBUTION] = LAPLACE
        else:
            raise NotImplementedError(
                f"Objective prior type {prior_type} is not implemented."
            )

        new_observable_dicts.append(new_observable)

        # add measurement
        # we could just use any condition and time point since the parameter
        # value is constant. however, using an existing timepoint and
        # (preequilibrationConditionId+)simulationConditionId will avoid
        # requiring extra simulations and solver stops in tools that do not
        # check for time dependency of the observable. we use the first
        # condition/timepoint from the measurement table
        new_measurement = {
            OBSERVABLE_ID: new_obs_id,
            TIME: problem.measurement_df[TIME].iloc[0],
            MEASUREMENT: prior_parameters[0],
            NOISE_PARAMETERS: prior_parameters[1],
            SIMULATION_CONDITION_ID: new_problem.measurement_df[
                SIMULATION_CONDITION_ID
            ].iloc[0],
        }
        if PREEQUILIBRATION_CONDITION_ID in new_problem.measurement_df:
            new_measurement[PREEQUILIBRATION_CONDITION_ID] = (
                new_problem.measurement_df[PREEQUILIBRATION_CONDITION_ID].iloc[
                    0
                ]
            )
        new_measurement_dicts.append(new_measurement)

        # remove prior from parameter table
        new_problem.parameter_df.loc[parameter_id, OBJECTIVE_PRIOR_TYPE] = (
            np.nan
        )
        new_problem.parameter_df.loc[
            parameter_id, OBJECTIVE_PRIOR_PARAMETERS
        ] = np.nan

    new_problem.observable_df = pd.concat(
        [
            new_problem.observable_df,
            pd.DataFrame(new_observable_dicts).set_index(OBSERVABLE_ID),
        ]
    )
    new_problem.measurement_df = pd.concat(
        [
            new_problem.measurement_df,
            pd.DataFrame(new_measurement_dicts),
        ],
        ignore_index=True,
    )
    return new_problem
