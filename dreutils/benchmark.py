
import os
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants
import dreutils.constants
import pandas as pd
import json
import glob
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

class BenchmarkTool(BaseCommandLineTool):
    """
    Runs benchmark pipeline
    """
    COMMAND = 'benchmark'

    def __init__(self, theargs):
        """

        :param theargs: command line arguments as a dict
                        should have the following values:
                        {'outdir': <OUTPUT RO-CRATE PATH>,
                         'predictions_rocrate': <PREDICTIONS RO-CRATE PATH>,
                         '
        :type theargs: dict
        """
        super().__init__(theargs)

    def _get_test_rocrates_map(self):
        """

        """
        results = {}
        with open(self._theargs['input_test_rocrates'], 'r') as f:
            for line in f:
                fp = os.path.abspath(line.strip())
                results[os.path.basename(fp)] = fp
        return results

    def _get_predictions_rocrates(self):
        """
        Gets predictions rocrates from prediction_rocrate,
        boy that is confusing.
        :return: map of predict rocrate name to path
        :rtype: dict
        """
        if not os.path.isdir(self._theargs['predictions_rocrate']):
            raise DreutilsError('predictions_rocrate is NOT a directory')

        results = {}
        predict_rocrate_path = os.path.abspath(os.path.join(self._theargs['predictions_rocrate'],
                                                            dreutils.constants.PREDICTIONS_DIRECTORY))

        if not os.path.isdir(predict_rocrate_path):
            raise DreutilsError('predictions_rocrate is NOT a directory')

        for entry in os.listdir(predict_rocrate_path):
            fp = os.path.join(predict_rocrate_path, entry)
            if not os.path.isdir(fp):
                continue
            results[entry] = fp
        return results

    def _evaluate_predictions(self, predict_rocrates_map, test_rocrates_map):
        """
        Evaluates predictions.
        """
        results_df = pd.DataFrame(columns=['predict_rocrate_name', 'test_rocrate_name', 'pearson_correlation', 'spearman_correlation'])
        for predict_rocrate_name, predict_rocrate_path in predict_rocrates_map.items():
            # open the task_*_start.json file
            task_start_file = glob.glob(os.path.join(predict_rocrate_path, 'task_*_start.json'))[0]
            with open(task_start_file, 'r') as f:
                json_data = json.load(f)
            test_rocrate_name = json_data['commandlineargs']['input_crate']

            predict_df = pd.read_csv(os.path.join(predict_rocrate_path, 'test_predictions.txt'), sep='\t', header=None, names=['auc']   )
            test_df = pd.read_csv(os.path.join(test_rocrate_name, 'test_data.txt'), sep='\t', header=None, names=['cell', 'smiles', 'auc', 'dataset'])

            # calculate the pearson and spearman correlation between the predict_df and test_df
            pearson_correlation = predict_df['auc'].corr(test_df['auc'])
            spearman_correlation = predict_df['auc'].corr(test_df['auc'], method='spearman')
            new_row = {'predict_rocrate_name': predict_rocrate_name, 'test_rocrate_name': test_rocrate_name, 'pearson_correlation': pearson_correlation, 'spearman_correlation': spearman_correlation}
            results_df = pd.concat([results_df, pd.DataFrame([new_row])], ignore_index=True)
        return results_df

    def _plot_results(self, results_df, sort_by=None, max_labels=50, width_per_label=0.32):
        """
        Plots Pearson (left y) and Spearman (right y) vs. drug name (x).
        - sort_by: optionally 'pearson_correlation' or 'spearman_correlation' to sort bars along x
        - max_labels: show at most this many x tick labels (others are thinned)
        - width_per_label: inches added to figure width per drug (capped)
        """
        df = results_df.copy()

        # Optional sort to make the plot easier to scan. If not provided, default to Pearson.
        effective_sort = sort_by if sort_by in ("pearson_correlation", "spearman_correlation") else "pearson_correlation"
        df = df.sort_values(effective_sort, ascending=False, kind="mergesort")

        names = df["predict_rocrate_name"].astype(str).tolist()
        # Shorten noisy suffixes for readability on the x-axis
        names = [n.replace("_test_rocrate_elasticnet_drecmd", "") for n in names]
        pearson = df["pearson_correlation"].to_numpy()
        spearman = df["spearman_correlation"].to_numpy()
        n = len(df)

        x = np.arange(n)

        # Figure size scales with number of drugs, within bounds
        fig_w = min(60, max(12, n * max(0.22, width_per_label)))   # 12"–60"
        fig_h = 6.0

        fig, ax1 = plt.subplots(figsize=(fig_w, fig_h))
        # Left axis: Pearson
        point_size = 28 if n <= 50 else 18
        p_scatter = ax1.scatter(x, pearson, s=point_size, alpha=0.9, linewidths=0, marker="o")
        ax1.set_ylabel("Pearson correlation", labelpad=8)
        ax1.set_ylim(-1.0, 1.0)
        ax1.yaxis.grid(True, linestyle="--", alpha=0.35)

        # Right axis: Spearman
        ax2 = ax1.twinx()
        # Use visible stroke for "x" marker and a contrasting color so points are readable
        s_scatter = ax2.scatter(x, spearman, s=point_size, alpha=0.9, linewidths=0.8, marker="x", color="#d62728")
        ax2.set_ylabel("Spearman correlation", labelpad=8)
        ax2.set_ylim(-1.0, 1.0)

        # X axis ticks: thin labels to at most max_labels
        step = max(1, int(np.ceil(n / max_labels)))
        shown_idx = x[::step]
        ax1.set_xticks(shown_idx)
        ax1.set_xticklabels([names[i] for i in shown_idx], rotation=85, ha="right")
        ax1.set_xlim(-0.5, n - 0.5)
        ax1.set_xlabel("Drug name")

        # Zero reference line
        ax1.axhline(0.0, linestyle=":", alpha=0.5)

        # Legend (custom so it works with twin axes)
        legend_handles = [
            Line2D([0], [0], marker="o", linestyle="None", label="Pearson"),
            Line2D([0], [0], marker="x", linestyle="None", label="Spearman", markeredgewidth=1.2, color="#d62728"),
        ]
        ax1.legend(handles=legend_handles, loc="upper left", frameon=False)

        # Extra bottom margin for rotated labels
        plt.subplots_adjust(bottom=0.28)

        outdir = self._theargs["outdir"]
        os.makedirs(outdir, exist_ok=True)
        png_path = os.path.join(outdir, "results.png")
        svg_path = os.path.join(outdir, "results.svg")

        plt.savefig(png_path, dpi=400, bbox_inches="tight")
        # Also emit an SVG for zoomable inspection
        plt.savefig(svg_path, bbox_inches="tight")
        plt.close()

    def run(self):
        """

        :return:
        """
        exitcode = 99
        try:
            # The line below creates output RO-Crate
            # The path to this output RO-Crate can be
            # found in self._theargs['outdir']
            self._initialize_rocrate()
            predict_rocrates_map = self._get_predictions_rocrates()
            # print(predict_rocrates_map)

            test_rocrates_map = self._get_test_rocrates_map()
            # print(test_rocrates_map)

            # TODO: add code to evaluate/benchmark
            #       predictions found in self._theargs['input']
            #       RO-Crate aka folder

            
            results_df = self._evaluate_predictions(predict_rocrates_map, test_rocrates_map)

            # save the results_df to a csv file
            results_df.to_csv(os.path.join(self._theargs['outdir'], 'results.csv'), index=False)

            self._plot_results(results_df)

            # The line below registers the computation
            # performed by this tool into the RO-Crate
            # metadata
            self._finalize_rocrate()
            return exitcode
        finally:
            # write a task finish file
            self._write_task_finish_json(exitcode)
        return 0

    def add_subparser(subparsers):
        """

        :return:
        """
        desc = """

        Version {version}

        {cmd} prints Hello world and exits
        """.format(version=dreutils.__version__,
                   cmd=BenchmarkTool.COMMAND)

        parser = subparsers.add_parser(BenchmarkTool.COMMAND,
                                       help='Benchmarks predictions on trained DRE models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)
        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')

        parser.add_argument('--input_test_rocrates',
                            help='File listing directories of test RO-Crates, one per line')
        parser.add_argument('--predictions_rocrate',
                            help='RO-Crate where prediction was run')

        return parser
