"""PEtab visualization plotter classes"""

import os
from abc import ABC, abstractmethod

import matplotlib.axes
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

from ..C import *
from .plotting import DataPlot, DataProvider, DataSeries, Figure, Subplot

__all__ = ["Plotter", "MPLPlotter", "SeabornPlotter"]


#: Line style (:class:`matplotlib.lines.Line2D` options) for the measurement
#  data in line plots
measurement_line_kwargs = {
    "linestyle": "-.",
    "marker": "x",
    "markersize": 10,
}
#: Line style (:class:`matplotlib.lines.Line2D` options) for the simulation
#  data in line plots
simulation_line_kwargs = {
    "linestyle": "-",
    "marker": "o",
    "markersize": 10,
}


class Plotter(ABC):
    """
    Plotter abstract base class.

    Attributes
    ----------
    figure:
        Figure instance that serves as a markup for the figure that
        should be generated
    data_provider:
        Data provider
    """

    def __init__(self, figure: Figure, data_provider: DataProvider):
        self.figure = figure
        self.data_provider = data_provider

    @abstractmethod
    def generate_figure(
        self, subplot_dir: str | None = None
    ) -> dict[str, plt.Subplot] | None:
        pass


class MPLPlotter(Plotter):
    """
    Matplotlib wrapper
    """

    def __init__(self, figure: Figure, data_provider: DataProvider):
        super().__init__(figure, data_provider)

    @staticmethod
    def _error_column_for_plot_type_data(plot_type_data: str) -> str | None:
        """Translate PEtab plotTypeData value to column name of internal
        data representation

        Parameters
        ----------
        plot_type_data: PEtab plotTypeData value (the way replicates should be
            handled)

        Returns
        -------
        Name of corresponding column
        """
        if plot_type_data == MEAN_AND_SD:
            return "sd"
        if plot_type_data == MEAN_AND_SEM:
            return "sem"
        if plot_type_data == PROVIDED:
            return "noise_model"
        return None

    def generate_lineplot(
        self,
        ax: matplotlib.axes.Axes,
        dataplot: DataPlot,
        plotTypeData: str,
        splitaxes_params: dict,
    ) -> tuple[matplotlib.axes.Axes, matplotlib.axes.Axes]:
        """
        Generate line plot.

        It is possible to plot only data or only simulation or both.

        Parameters
        ----------
        ax:
            Axis object.
        dataplot:
            Visualization settings for the plot.
        plotTypeData:
            Specifies how replicates should be handled.
        splitaxes_params:

        """
        simu_color = None
        (
            measurements_to_plot,
            simulations_to_plot,
        ) = self.data_provider.get_data_to_plot(
            dataplot, plotTypeData == PROVIDED
        )
        noise_col = self._error_column_for_plot_type_data(plotTypeData)

        label_base = dataplot.legendEntry

        # check if t_inf is there
        # todo: if only t_inf, adjust appearance for that case
        plot_at_t_inf = (
            measurements_to_plot is not None and measurements_to_plot.inf_point
        ) or (
            simulations_to_plot is not None and simulations_to_plot.inf_point
        )

        if (
            measurements_to_plot is not None
            and not measurements_to_plot.data_to_plot.empty
        ):
            # plotting all measurement data

            p = None
            if plotTypeData == REPLICATE:
                replicates = np.stack(
                    measurements_to_plot.data_to_plot.repl.values
                )
                # sorts according to ascending order of conditions
                cond, replicates = zip(
                    *sorted(
                        zip(
                            measurements_to_plot.conditions,
                            replicates,
                            strict=True,
                        )
                    ),
                    strict=True,
                )
                replicates = np.stack(replicates)

                if replicates.ndim == 1:
                    replicates = np.expand_dims(replicates, axis=1)

                # plot first replicate
                p = ax.plot(
                    cond,
                    replicates[:, 0],
                    label=label_base,
                    **measurement_line_kwargs,
                )

                # plot other replicates with the same color
                ax.plot(
                    cond,
                    replicates[:, 1:],
                    **measurement_line_kwargs,
                    color=p[0].get_color(),
                )

            # construct errorbar-plots: noise specified above
            else:
                # sorts according to ascending order of conditions
                scond, smean, snoise = zip(
                    *sorted(
                        zip(
                            measurements_to_plot.conditions,
                            measurements_to_plot.data_to_plot["mean"],
                            measurements_to_plot.data_to_plot[noise_col],
                            strict=True,
                        )
                    ),
                    strict=True,
                )

                if np.inf in scond:
                    # remove inf point
                    scond = scond[:-1]
                    smean = smean[:-1]
                    snoise = snoise[:-1]

                if len(scond) > 0 and len(smean) > 0 and len(snoise) > 0:
                    # if only t=inf there will be nothing to plot
                    p = ax.errorbar(
                        scond,
                        smean,
                        snoise,
                        label=label_base,
                        **measurement_line_kwargs,
                    )

            # simulations should have the same colors if both measurements
            # and simulations are plotted
            simu_color = p[0].get_color() if p else None

        # construct simulation plot
        if (
            simulations_to_plot is not None
            and not simulations_to_plot.data_to_plot.empty
        ):
            # markers will be displayed only for points that have measurement
            # counterpart
            if measurements_to_plot is not None:
                meas_conditions = (
                    measurements_to_plot.conditions.to_numpy()
                    if isinstance(measurements_to_plot.conditions, pd.Series)
                    else measurements_to_plot.conditions
                )
                every = [
                    condition in meas_conditions
                    for condition in simulations_to_plot.conditions
                ]
            else:
                every = None

            # sorts according to ascending order of conditions
            xs, ys = map(
                list,
                zip(
                    *sorted(
                        zip(
                            simulations_to_plot.conditions,
                            simulations_to_plot.data_to_plot["mean"],
                            strict=True,
                        )
                    ),
                    strict=True,
                ),
            )

            if np.inf in xs:
                # remove inf point
                xs = xs[:-1]
                ys = ys[:-1]
                every = every[:-1] if every else None

            if len(xs) > 0 and len(ys) > 0:
                p = ax.plot(
                    xs,
                    ys,
                    markevery=every,
                    label=label_base + " simulation",
                    color=simu_color,
                    **simulation_line_kwargs,
                )
                # lines at t=inf should have the same colors also in case
                # only simulations are plotted
                simu_color = p[0].get_color()

        # plot inf points
        if plot_at_t_inf:
            ax, splitaxes_params["ax_inf"] = self._line_plot_at_t_inf(
                ax,
                plotTypeData,
                measurements_to_plot,
                simulations_to_plot,
                noise_col,
                label_base,
                splitaxes_params,
                color=simu_color,
            )

        return ax, splitaxes_params["ax_inf"]

    def generate_barplot(
        self,
        ax: "matplotlib.pyplot.Axes",
        dataplot: DataPlot,
        plotTypeData: str,
    ) -> None:
        """
        Generate barplot.

        Parameters
        ----------
        ax:
            Axis object.
        dataplot:
            Visualization settings for the plot.
        plotTypeData:
            Specifies how replicates should be handled.
        """
        # TODO: plotTypeData == REPLICATE?
        noise_col = self._error_column_for_plot_type_data(plotTypeData)

        (
            measurements_to_plot,
            simulations_to_plot,
        ) = self.data_provider.get_data_to_plot(
            dataplot, plotTypeData == PROVIDED
        )

        x_name = dataplot.legendEntry

        if simulations_to_plot:
            bar_kwargs = {
                "align": "edge",
                "width": -1 / 3,
            }
        else:
            bar_kwargs = {
                "align": "center",
                "width": 2 / 3,
            }

        color = plt.rcParams["axes.prop_cycle"].by_key()["color"][0]

        if measurements_to_plot is not None:
            ax.bar(
                x_name,
                measurements_to_plot.data_to_plot["mean"],
                yerr=measurements_to_plot.data_to_plot[noise_col],
                color=color,
                **bar_kwargs,
                label="measurement",
            )

        if simulations_to_plot is not None:
            bar_kwargs["width"] = -bar_kwargs["width"]
            ax.bar(
                x_name,
                simulations_to_plot.data_to_plot["mean"],
                color="white",
                edgecolor=color,
                **bar_kwargs,
                label="simulation",
            )

    def generate_scatterplot(
        self,
        ax: "matplotlib.pyplot.Axes",
        dataplot: DataPlot,
        plotTypeData: str,
    ) -> None:
        """
        Generate scatterplot.

        Parameters
        ----------
        ax:
            Axis object.
        dataplot:
            Visualization settings for the plot.
        plotTypeData:
            Specifies how replicates should be handled.
        """
        (
            measurements_to_plot,
            simulations_to_plot,
        ) = self.data_provider.get_data_to_plot(
            dataplot, plotTypeData == PROVIDED
        )

        if simulations_to_plot is None or measurements_to_plot is None:
            raise NotImplementedError(
                "Both measurements and simulation data "
                "are needed for scatter plots"
            )
        ax.scatter(
            measurements_to_plot.data_to_plot["mean"],
            simulations_to_plot.data_to_plot["mean"],
            label=getattr(dataplot, LEGEND_ENTRY),
        )
        self._square_plot_equal_ranges(ax)

    def generate_subplot(
        self,
        fig: matplotlib.figure.Figure,
        ax: matplotlib.axes.Axes,
        subplot: Subplot,
    ) -> None:
        """
        Generate subplot based on markup provided by subplot.

        Parameters
        ----------
        fig:
            Figure object.
        ax:
            Axis object.
        subplot:
            Subplot visualization settings.
        """
        # set yScale
        if subplot.yScale == LIN:
            ax.set_yscale("linear")
        elif subplot.yScale == LOG10:
            ax.set_yscale("log")
        elif subplot.yScale == LOG:
            ax.set_yscale("log", base=np.e)

        if subplot.plotTypeSimulation == BAR_PLOT:
            for data_plot in subplot.data_plots:
                self.generate_barplot(ax, data_plot, subplot.plotTypeData)

            # get rid of duplicate legends
            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles, strict=True))
            ax.legend(by_label.values(), by_label.keys())

            x_names = [x.legendEntry for x in subplot.data_plots]
            ax.set_xticks(range(len(x_names)))
            ax.set_xticklabels(x_names)

            for label in ax.get_xmajorticklabels():
                label.set_rotation(30)
                label.set_horizontalalignment("right")
        elif subplot.plotTypeSimulation == SCATTER_PLOT:
            for data_plot in subplot.data_plots:
                self.generate_scatterplot(ax, data_plot, subplot.plotTypeData)
        else:
            # set xScale
            if subplot.xScale == LIN:
                ax.set_xscale("linear")
            elif subplot.xScale == LOG10:
                ax.set_xscale("log")
            elif subplot.xScale == LOG:
                ax.set_xscale("log", base=np.e)
            # equidistant
            elif subplot.xScale == "order":
                ax.set_xscale("linear")
                # check if conditions are monotone decreasing or increasing
                if np.all(np.diff(subplot.conditions) < 0):
                    # monot. decreasing -> reverse
                    xlabel = subplot.conditions[::-1]
                    conditions = range(len(subplot.conditions))[::-1]
                    ax.set_xticks(range(len(conditions)), xlabel)
                elif np.all(np.diff(subplot.conditions) > 0):
                    xlabel = subplot.conditions
                    conditions = range(len(subplot.conditions))
                    ax.set_xticks(range(len(conditions)), xlabel)
                else:
                    raise ValueError(
                        "Error: x-conditions do not coincide, "
                        "some are mon. increasing, some "
                        "monotonically decreasing"
                    )

            splitaxes_params = self._preprocess_splitaxes(fig, ax, subplot)
            for data_plot in subplot.data_plots:
                ax, splitaxes_params["ax_inf"] = self.generate_lineplot(
                    ax,
                    data_plot,
                    subplot.plotTypeData,
                    splitaxes_params=splitaxes_params,
                )
            if splitaxes_params["ax_inf"] is not None:
                self._postprocess_splitaxes(
                    ax, splitaxes_params["ax_inf"], splitaxes_params["t_inf"]
                )

        # show 'e' as basis not 2.7... in natural log scale cases
        def ticks(y, _):
            return rf"$e^{{{np.log(y):.0f}}}$"

        if subplot.xScale == LOG:
            ax.xaxis.set_major_formatter(mtick.FuncFormatter(ticks))
        if subplot.yScale == LOG:
            ax.yaxis.set_major_formatter(mtick.FuncFormatter(ticks))

        if subplot.plotTypeSimulation != BAR_PLOT:
            ax.legend()
        ax.set_title(subplot.plotName)
        if subplot.xlim:
            ax.set_xlim(subplot.xlim)
        if subplot.ylim:
            ax.set_ylim(subplot.ylim)
        ax.autoscale_view()

        # Beautify plots
        ax.set_xlabel(subplot.xLabel)
        ax.set_ylabel(subplot.yLabel)

    def generate_figure(
        self,
        subplot_dir: str | None = None,
        format_: str = "png",
    ) -> dict[str, plt.Subplot] | None:
        """
        Generate the full figure based on the markup in the figure attribute.

        Parameters
        ----------
        subplot_dir:
            A path to the folder where single subplots should be saved.
            PlotIDs will be taken as file names.
        format_:
            File format for the generated figure.
            (See :py:func:`matplotlib.pyplot.savefig` for supported options).

        Returns
        -------
        ax:
            Axis object of the created plot.
        None:
            In case subplots are saved to file.
        """
        if subplot_dir is None:
            # compute, how many rows and columns we need for the subplots
            num_row = int(np.round(np.sqrt(self.figure.num_subplots)))
            num_col = int(np.ceil(self.figure.num_subplots / num_row))

            fig, axes = plt.subplots(
                num_row, num_col, squeeze=False, figsize=self.figure.size
            )
            fig.set_layout_engine("tight")

            for ax in axes.flat[self.figure.num_subplots :]:
                ax.remove()

            axes = dict(
                zip(
                    [plot.plotId for plot in self.figure.subplots],
                    axes.flat,
                    strict=False,
                )
            )

        for subplot in self.figure.subplots:
            if subplot_dir is not None:
                fig, ax = plt.subplots(figsize=self.figure.size)
                fig.set_layout_engine("tight")
            else:
                ax = axes[subplot.plotId]

            try:
                self.generate_subplot(fig, ax, subplot)
            except Exception as e:
                raise RuntimeError(
                    f"Error plotting {getattr(subplot, PLOT_ID)}."
                ) from e

            if subplot_dir is not None:
                # TODO: why this doesn't work?
                plt.tight_layout()
                plt.savefig(
                    os.path.join(subplot_dir, f"{subplot.plotId}.{format_}")
                )
                plt.close()

        if subplot_dir is None:
            # TODO: why this doesn't work?
            plt.tight_layout()
            return axes

    @staticmethod
    def _square_plot_equal_ranges(
        ax: "matplotlib.pyplot.Axes", lim: list | tuple | None = None
    ) -> "matplotlib.pyplot.Axes":
        """
        Square plot with equal range for scatter plots.

        Returns
        -------
            Updated axis object.
        """
        ax.axis("square")

        if lim is None:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            lim = [np.min([xlim[0], ylim[0]]), np.max([xlim[1], ylim[1]])]

        ax.set_xlim(lim)
        ax.set_ylim(lim)

        # Same tick mark on x and y
        ax.yaxis.set_major_locator(ax.xaxis.get_major_locator())

        return ax

    @staticmethod
    def _line_plot_at_t_inf(
        ax: matplotlib.axes.Axes,
        plotTypeData: str,
        measurements_to_plot: DataSeries,
        simulations_to_plot: DataSeries,
        noise_col: str,
        label_base: str,
        split_axes_params: dict,
        color=None,
    ) -> tuple[matplotlib.axes.Axes, matplotlib.axes.Axes]:
        """
        Plot data at t=inf.

        Parameters
        ----------
        ax:
            Axis object for the data corresponding to the finite timepoints.
        plotTypeData:
            The way replicates should be handled.
        measurements_to_plot:
            Measurements to plot.
        simulations_to_plot:
            Simulations to plot.
        noise_col:
            The name of the error column for plot_type_data.
        label_base:
            Label base.
        split_axes_params:
            A dictionary of split axes parameters with
            - Axis object for the data corresponding to t=inf
            - Time value that represents t=inf
            - left and right limits for the axis where the data corresponding
            to the finite timepoints is plotted
        color:
            Line color.

        Returns
        -------
        Two axis objects: for the data corresponding to the finite timepoints
        and for the data corresponding to t=inf
        """
        ax_inf = split_axes_params["ax_inf"]
        t_inf = split_axes_params["t_inf"]
        ax_finite_right_limit = split_axes_params["ax_finite_right_limit"]
        ax_left_limit = split_axes_params["ax_left_limit"]

        timepoints_inf = [
            ax_finite_right_limit,
            t_inf,
            ax_finite_right_limit
            + (ax_finite_right_limit - ax_left_limit) * 0.2,
        ]

        # plot measurements
        if measurements_to_plot is not None and measurements_to_plot.inf_point:
            measurements_data_to_plot_inf = (
                measurements_to_plot.data_to_plot.loc[np.inf]
            )

            if plotTypeData == REPLICATE:
                p = None
                if plotTypeData == REPLICATE:
                    replicates = measurements_data_to_plot_inf.repl
                    if replicates.ndim == 0:
                        replicates = np.expand_dims(replicates, axis=0)

                    # plot first replicate
                    p = ax_inf.plot(
                        timepoints_inf,
                        [replicates[0]] * 3,
                        markevery=[1],
                        label=label_base + " simulation",
                        color=color,
                        **measurement_line_kwargs,
                    )

                    # plot other replicates with the same color
                    ax_inf.plot(
                        timepoints_inf,
                        [replicates[1:]] * 3,
                        markevery=[1],
                        color=p[0].get_color(),
                        **measurement_line_kwargs,
                    )
            else:
                p = ax_inf.plot(
                    [timepoints_inf[0], timepoints_inf[2]],
                    [
                        measurements_data_to_plot_inf["mean"],
                        measurements_data_to_plot_inf["mean"],
                    ],
                    color=color,
                    **measurement_line_kwargs,
                )
                ax_inf.errorbar(
                    t_inf,
                    measurements_data_to_plot_inf["mean"],
                    measurements_data_to_plot_inf[noise_col],
                    label=label_base + " simulation",
                    color=p[0].get_color(),
                    **measurement_line_kwargs,
                )

            if color is None:
                # in case no color was provided from finite time points
                # plot and measurements are available corresponding
                # simulation should have the same color
                color = p[0].get_color()

        # plot simulations
        if simulations_to_plot is not None and simulations_to_plot.inf_point:
            simulations_data_to_plot_inf = (
                simulations_to_plot.data_to_plot.loc[np.inf]
            )

            if plotTypeData == REPLICATE:
                replicates = simulations_data_to_plot_inf.repl
                if replicates.ndim == 0:
                    replicates = np.expand_dims(replicates, axis=0)

                # plot first replicate
                p = ax_inf.plot(
                    timepoints_inf,
                    [replicates[0]] * 3,
                    markevery=[1],
                    label=label_base,
                    color=color,
                    **simulation_line_kwargs,
                )

                # plot other replicates with the same color
                ax_inf.plot(
                    timepoints_inf,
                    [replicates[1:]] * 3,
                    markevery=[1],
                    color=p[0].get_color(),
                    **simulation_line_kwargs,
                )
            else:
                ax_inf.plot(
                    timepoints_inf,
                    [simulations_data_to_plot_inf["mean"]] * 3,
                    markevery=[1],
                    color=color,
                    **simulation_line_kwargs,
                )

        ax.set_xlim(right=ax_finite_right_limit)
        return ax, ax_inf

    @staticmethod
    def _postprocess_splitaxes(
        ax: matplotlib.axes.Axes, ax_inf: matplotlib.axes.Axes, t_inf: float
    ) -> None:
        """
        Postprocess the splitaxes: set axes limits, turn off unnecessary
        ticks and plot dashed lines highlighting the gap in the x axis.

        Parameters
        ----------
        ax:
            Axis object for the data corresponding to the finite timepoints.
        ax_inf:
            Axis object for the data corresponding to t=inf.
        t_inf:
            Time value that represents t=inf
        """
        ax_inf.tick_params(left=False, labelleft=False)
        ax_inf.spines["left"].set_visible(False)
        ax_inf.set_xticks([t_inf])
        ax_inf.set_xticklabels([r"$t_{\infty}$"])

        bottom, top = ax.get_ylim()
        left, right = ax.get_xlim()
        ax.spines["right"].set_visible(False)
        ax_inf.set_xlim(right, right + (right - left) * 0.2)
        d = (top - bottom) * 0.02
        ax_inf.vlines(
            x=right, ymin=bottom + d, ymax=top - d, ls="--", color="gray"
        )  # right
        ax.vlines(
            x=right, ymin=bottom + d, ymax=top - d, ls="--", color="gray"
        )  # left
        ax_inf.set_ylim(bottom, top)
        ax.set_ylim(bottom, top)

    def _preprocess_splitaxes(
        self,
        fig: matplotlib.figure.Figure,
        ax: matplotlib.axes.Axes,
        subplot: Subplot,
    ) -> dict:
        """
        Prepare splitaxes if data at t=inf should be plotted: compute left and
        right limits for the axis where the data corresponding to the finite
        timepoints will be plotted, compute time point that will represent
        t=inf on the plot, create additional axes for plotting data at t=inf.
        """

        def check_data_to_plot(
            data_to_plot: DataSeries,
        ) -> tuple[bool, float | None, float]:
            """
            Check if there is data available at t=inf and compute maximum and
            minimum finite time points that need to be plotted corresponding
            to a dataplot.
            """
            contains_inf = False
            max_finite_cond, min_cond = None, np.inf
            if data_to_plot is not None and len(data_to_plot.conditions):
                contains_inf = np.inf in data_to_plot.conditions
                finite_conditions = data_to_plot.conditions[
                    data_to_plot.conditions != np.inf
                ]
                max_finite_cond = (
                    np.max(finite_conditions)
                    if finite_conditions.size
                    else None
                )
                min_cond = min(data_to_plot.conditions)
            return contains_inf, max_finite_cond, min_cond

        splitaxes = False
        ax_inf = None
        t_inf, ax_finite_right_limit, ax_left_limit = None, None, np.inf
        for dataplot in subplot.data_plots:
            (
                measurements_to_plot,
                simulations_to_plot,
            ) = self.data_provider.get_data_to_plot(
                dataplot, subplot.plotTypeData == PROVIDED
            )

            contains_inf_m, max_finite_cond_m, min_cond_m = check_data_to_plot(
                measurements_to_plot
            )
            contains_inf_s, max_finite_cond_s, min_cond_s = check_data_to_plot(
                simulations_to_plot
            )

            if max_finite_cond_m is not None:
                ax_finite_right_limit = (
                    max(ax_finite_right_limit, max_finite_cond_m)
                    if ax_finite_right_limit is not None
                    else max_finite_cond_m
                )
            if max_finite_cond_s is not None:
                ax_finite_right_limit = (
                    max(ax_finite_right_limit, max_finite_cond_s)
                    if ax_finite_right_limit is not None
                    else max_finite_cond_s
                )

            ax_left_limit = min(ax_left_limit, min(min_cond_m, min_cond_s))
            # check if t=inf is contained in any data to be plotted on the
            # subplot
            if not splitaxes:
                splitaxes = contains_inf_m or contains_inf_s

        if splitaxes:
            # if t=inf is the only time point in measurements and simulations
            # ax_finite_right_limit will be None and ax_left_limit will be
            # equal to np.inf
            if ax_finite_right_limit is None and ax_left_limit == np.inf:
                ax_finite_right_limit = 10
                ax_left_limit = 0
            t_inf = (
                ax_finite_right_limit
                + (ax_finite_right_limit - ax_left_limit) * 0.1
            )
            # create axes for t=inf
            divider = make_axes_locatable(ax)
            ax_inf = divider.new_horizontal(size="10%", pad=0.3)
            fig.add_axes(ax_inf)

        return {
            "ax_inf": ax_inf,
            "t_inf": t_inf,
            "ax_finite_right_limit": ax_finite_right_limit,
            "ax_left_limit": ax_left_limit,
        }


class SeabornPlotter(Plotter):
    """
    Seaborn wrapper.
    """

    def __init__(self, figure: Figure, data_provider: DataProvider):
        super().__init__(figure, data_provider)

    def generate_figure(
        self, subplot_dir: str | None = None
    ) -> dict[str, plt.Subplot] | None:
        pass
