
import os
import sys
import re
import aixport
from aixport.basecmdtool import BaseCommandLineTool
from aixport.exceptions import AIxPORTError
import cellmaps_utils.constants
import aixport.constants
import pandas as pd
import json
import glob
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import joblib


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
        :type theargs: dict
        """
        super().__init__(theargs)

    def _get_test_rocrates_map(self):
        """
        todo
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
        predictions_rocrate_arg = self._theargs['predictions_rocrate']
        if not os.path.isdir(predictions_rocrate_arg):
            raise AIxPORTError(f'predictions_rocrate "{predictions_rocrate_arg}" is NOT a directory or does not exist')

        results = {}
        predict_rocrate_path = os.path.abspath(os.path.join(predictions_rocrate_arg,
                                                            aixport.constants.PREDICTIONS_DIRECTORY))

        if not os.path.isdir(predict_rocrate_path):
            raise AIxPORTError(f'predictions subdirectory not found at "{predict_rocrate_path}". '
                               f'Make sure you have run the predict command first. '
                               f'The predictions_rocrate argument should point to the output directory from the predict command.')

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
        results_df = pd.DataFrame(columns=['predict_rocrate_name', 'test_rocrate_name',
                                           'drug_name', 'algorithm_name',
                                           'pearson_correlation', 'spearman_correlation',
                                           'total_samples'])
        for predict_rocrate_name, predict_rocrate_path in predict_rocrates_map.items():
            # open the task_*_start.json file
            task_start_file = glob.glob(os.path.join(predict_rocrate_path, 'task_*_start.json'))[0]
            with open(task_start_file, 'r') as f:
                json_data = json.load(f)
            test_rocrate_name = json_data['commandlineargs']['input_crate']
            drug_name, algorithm_name = self._parse_predict_rocrate_name(predict_rocrate_name)
            total_samples = self._get_total_samples(test_rocrate_name)

            predictions_file = os.path.join(predict_rocrate_path, 'test_predictions.txt')
            if not os.path.isfile(predictions_file):
                alt_predictions_file = os.path.join(predict_rocrate_path, 'predictions.txt')
                if os.path.isfile(alt_predictions_file):
                    predictions_file = alt_predictions_file
                else:
                    raise AIxPORTError('Missing predictions file in ' + predict_rocrate_path +
                                        '; expected test_predictions.txt or predictions.txt')

            predict_df = pd.read_csv(predictions_file, sep='\t', header=None, names=['auc'])
            test_df = pd.read_csv(os.path.join(test_rocrate_name, 'test_data.txt'), sep='\t', header=None, names=['cell', 'smiles', 'auc', 'dataset'])

            # calculate the pearson and spearman correlation between the predict_df and test_df
            pearson_correlation = predict_df['auc'].corr(test_df['auc'])
            spearman_correlation = predict_df['auc'].corr(test_df['auc'], method='spearman')
            new_row = {'predict_rocrate_name': predict_rocrate_name,
                       'test_rocrate_name': test_rocrate_name,
                       'drug_name': drug_name,
                       'algorithm_name': algorithm_name,
                       'pearson_correlation': pearson_correlation,
                       'spearman_correlation': spearman_correlation,
                       'total_samples': total_samples}
            results_df = pd.concat([results_df, pd.DataFrame([new_row])], ignore_index=True)
        return results_df

    def _plot_results(self, results_df, sort_by=None, max_labels=50, width_per_label=0.32):
        """
        Plots Spearman vs. drug name (x).
        - sort_by: optionally 'pearson_correlation' or 'spearman_correlation' to sort bars along x
        - max_labels: show at most this many x tick labels (others are thinned)
        - width_per_label: inches added to figure width per drug (capped)
        """
        df = results_df.copy()

        # Optional sort to make the plot easier to scan. If not provided, default to Pearson.
        effective_sort = sort_by if sort_by in ("pearson_correlation", "spearman_correlation") else "pearson_correlation"
        df = df.sort_values(effective_sort, ascending=False, kind="mergesort")

        drugs = df["drug_name"].fillna(df["predict_rocrate_name"]).astype(str).tolist()
        total_samples_map = {}
        for _, row in df.iterrows():
            drug = row.get("drug_name") or row.get("predict_rocrate_name")
            total = row.get("total_samples")
            if drug and drug not in total_samples_map and pd.notna(total):
                total_samples_map[str(drug)] = int(total)
        spearman = df["spearman_correlation"].to_numpy()
        algos = df["algorithm_name"].fillna("unknown").astype(str).tolist()
        unique_algos = sorted(set(algos))
        unique_drugs = []
        for drug in drugs:
            if drug not in unique_drugs:
                unique_drugs.append(drug)
        color_cycle = plt.rcParams.get("axes.prop_cycle").by_key().get("color", [])
        algo_colors = {}
        for idx, algo in enumerate(unique_algos):
            color = color_cycle[idx % len(color_cycle)] if color_cycle else None
            algo_colors[algo] = color
        n = len(df)
        group_spacing = 1.6
        x_base = {drug: idx * group_spacing for idx, drug in enumerate(unique_drugs)}
        x = np.array([x_base[drug] for drug in drugs], dtype=float)
        if len(unique_algos) > 1:
            step = min(0.35, 1.0 / len(unique_algos))
            offsets = {algo: (i - (len(unique_algos) - 1) / 2.0) * step
                       for i, algo in enumerate(unique_algos)}
            x = np.array([x[idx] + offsets[algos[idx]] for idx in range(n)], dtype=float)

        # Figure size scales with number of drugs, within bounds
        fig_w = min(80, max(14, len(unique_drugs) * max(0.4, width_per_label)))
        fig_h = 6.0

        fig, ax1 = plt.subplots(figsize=(fig_w, fig_h))
        point_size = 28 if n <= 50 else 18
        point_colors = [algo_colors.get(algo) for algo in algos]
        ax1.scatter(x, spearman, s=point_size, alpha=0.9, linewidths=0.8, marker="o", c=point_colors)
        ax1.set_ylabel("Spearman correlation", labelpad=8)
        ax1.set_ylim(-1.0, 1.0)
        ax1.yaxis.grid(True, linestyle="--", alpha=0.35)

        # X axis ticks: thin labels to at most max_labels
        step = max(1, int(np.ceil(len(unique_drugs) / max_labels)))
        shown_idx = np.arange(len(unique_drugs))[::step]
        ax1.set_xticks([idx * group_spacing for idx in shown_idx])
        labels = []
        for idx in shown_idx:
            drug = unique_drugs[idx]
            total = total_samples_map.get(drug)
            if total is not None:
                labels.append(f"{drug} (n={total})")
            else:
                labels.append(f"{drug} (n=?)")
        ax1.set_xticklabels(labels, rotation=85, ha="right")
        ax1.set_xlim(-0.5, (len(unique_drugs) - 0.5) * group_spacing)
        ax1.set_xlabel("Drug name (grouped)")

        # Zero reference line
        ax1.axhline(0.0, linestyle=":", alpha=0.5)
        for idx in range(len(unique_drugs)):
            ax1.axvline((idx * group_spacing) - (group_spacing / 2.0),
                        linestyle=":", alpha=0.2, linewidth=0.8)

        algo_handles = [
            Line2D([0], [0], marker="o", linestyle="None", label=algo, color=algo_colors[algo])
            for algo in unique_algos
        ]
        ax1.legend(handles=algo_handles, loc="upper left", frameon=False)

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

    def _extract_feature_importance(self, predict_rocrates_map, test_rocrates_map):
        """
        Extract feature importance (coefficients) from ElasticNet models and create cell lines x genes matrices.
        Creates matrices similar to cell2mutation.txt format showing feature importance per cell line.
        """
        try:
            # Get trained models directory from predictions rocrate
            predictions_rocrate = self._theargs['predictions_rocrate']
            
            # Try to find trainedmodels directory - check multiple possible locations
            possible_paths = [
                os.path.join(predictions_rocrate, '..', 'trainedmodels'),
                os.path.join(os.path.dirname(predictions_rocrate), 'trainedmodels'),
                os.path.join(predictions_rocrate, '..', '..', 'trainedmodels'),
            ]
            
            trainedmodels_dir = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    trainedmodels_dir = abs_path
                    break
            
            # Also check if trainedmodels.txt exists in predictions_rocrate
            trainedmodels_file = os.path.join(predictions_rocrate, 'trainedmodels.txt')
            if not trainedmodels_dir and os.path.exists(trainedmodels_file):
                # Read first line to get a model directory, then get parent
                with open(trainedmodels_file, 'r') as f:
                    first_line = f.readline().strip()
                    if first_line:
                        trainedmodels_dir = os.path.dirname(first_line)
            
            if not trainedmodels_dir or not os.path.exists(trainedmodels_dir):
                print(f"WARNING: Could not find trainedmodels directory, skipping feature importance extraction")
                return
            
            # Get reference files from first available test rocrate
            first_test_rocrate = list(test_rocrates_map.values())[0]
            gene2ind_path = os.path.join(first_test_rocrate, 'gene2ind.txt')
            cell2ind_path = os.path.join(first_test_rocrate, 'cell2ind.txt')
            
            if not os.path.exists(gene2ind_path) or not os.path.exists(cell2ind_path):
                print(f"WARNING: Could not find gene2ind.txt or cell2ind.txt, skipping feature importance extraction")
                return
            
            # Load gene and cell names
            gene_index = pd.read_csv(gene2ind_path, sep='\t', header=None, names=['I', 'G'])
            gene_list = gene_index['G'].tolist()
            num_genes = len(gene_list)
            
            cell_index = pd.read_csv(cell2ind_path, sep='\t', header=None, names=['I', 'C'])
            cell_list = cell_index['C'].tolist()
            num_cells = len(cell_list)
            
            # Process each drug and create cell lines x genes matrices
            outdir = self._theargs['outdir']
            
            for predict_rocrate_name, predict_rocrate_path in predict_rocrates_map.items():
                # Extract drug and algorithm name
                drug_name, algorithm_name = self._parse_predict_rocrate_name(predict_rocrate_name)
                if algorithm_name != 'elasticnet_drecmd':
                    continue
                
                # Get corresponding test rocrate to load cell features
                test_rocrate_path = None
                for test_name, test_path in test_rocrates_map.items():
                    if drug_name in test_name:
                        test_rocrate_path = test_path
                        break
                
                if not test_rocrate_path:
                    print(f"WARNING: Could not find test rocrate for {drug_name}, skipping")
                    continue
                
                # Find corresponding trained model
                model_dir_name = f"{drug_name}_train_rocrate_{algorithm_name}"
                model_dir = os.path.join(trainedmodels_dir, model_dir_name)
                model_path = os.path.join(model_dir, 'model.pkl')
                
                if not os.path.exists(model_path):
                    print(f"WARNING: Model not found at {model_path} for {drug_name}, skipping")
                    continue
                
                try:
                    # Load model
                    model = joblib.load(model_path)
                    coefficients = model.coef_
                    
                    # Load cell features from test rocrate
                    mutations = pd.read_csv(os.path.join(test_rocrate_path, 'cell2mutation.txt'), 
                                          header=None, names=gene_list)
                    cn_deletions = pd.read_csv(os.path.join(test_rocrate_path, 'cell2cndeletion.txt'), 
                                             header=None, names=gene_list)
                    cn_amplifications = pd.read_csv(os.path.join(test_rocrate_path, 'cell2cnamplification.txt'), 
                                                   header=None, names=gene_list)
                    
                    # Coefficients are arranged as: [gene1_mut, gene1_del, gene1_amp, gene2_mut, gene2_del, gene2_amp, ...]
                    # Reshape to (num_genes, 3)
                    coef_matrix = coefficients.reshape(num_genes, 3)
                    
                    # For each cell line, compute feature importance: 
                    # importance[cell, gene] = mut[cell, gene] * coef[gene, mut] + del[cell, gene] * coef[gene, del] + amp[cell, gene] * coef[gene, amp]
                    importance_mutation = mutations.values * coef_matrix[:, 0].reshape(1, -1)
                    importance_deletion = cn_deletions.values * coef_matrix[:, 1].reshape(1, -1)
                    importance_amplification = cn_amplifications.values * coef_matrix[:, 2].reshape(1, -1)
                    
                    # Sum across feature types for total importance
                    importance_total = importance_mutation + importance_deletion + importance_amplification
                    
                    # Create DataFrames with cell lines as rows and genes as columns
                    importance_total_df = pd.DataFrame(importance_total, index=cell_list, columns=gene_list)
                    importance_mutation_df = pd.DataFrame(importance_mutation, index=cell_list, columns=gene_list)
                    importance_deletion_df = pd.DataFrame(importance_deletion, index=cell_list, columns=gene_list)
                    importance_amplification_df = pd.DataFrame(importance_amplification, index=cell_list, columns=gene_list)
                    
                    # Save matrices (format similar to cell2mutation.txt - comma-separated, no headers)
                    drug_outdir = os.path.join(outdir, drug_name)
                    os.makedirs(drug_outdir, exist_ok=True)
                    
                    # Save as comma-separated (like cell2mutation.txt format)
                    importance_total_df.to_csv(os.path.join(drug_outdir, 'cell2importance.txt'), 
                                             sep=',', header=False, index=False)
                    importance_mutation_df.to_csv(os.path.join(drug_outdir, 'cell2importance_mutation.txt'), 
                                                  sep=',', header=False, index=False)
                    importance_deletion_df.to_csv(os.path.join(drug_outdir, 'cell2importance_deletion.txt'), 
                                                  sep=',', header=False, index=False)
                    importance_amplification_df.to_csv(os.path.join(drug_outdir, 'cell2importance_amplification.txt'), 
                                                       sep=',', header=False, index=False)
                    
                    # Also save with headers for easier reading
                    importance_total_df.to_csv(os.path.join(drug_outdir, 'cell2importance_with_headers.csv'), 
                                              sep='\t', header=True, index=True)
                    
                    print(f"Created feature importance matrices for {drug_name}: {num_cells} cell lines x {num_genes} genes")
                    
                except Exception as e:
                    print(f"WARNING: Error processing {drug_name}: {str(e)}, skipping")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"Feature importance matrices saved to {outdir}")
            
        except Exception as e:
            print(f"WARNING: Error extracting feature importance: {str(e)}")
            import traceback
            traceback.print_exc()

    def _parse_predict_rocrate_name(self, predict_rocrate_name):
        """
        Parse prediction rocrate directory name into drug and algorithm names.
        Expected format: <Drug>_test_rocrate_<algorithm>
        """
        match = re.match(r'^(?P<drug>.+)_test_rocrate_(?P<algo>.+)$', predict_rocrate_name)
        if match:
            return match.group('drug'), match.group('algo')
        return predict_rocrate_name, None

    def _get_total_samples(self, test_rocrate_path):
        """
        Determine total samples (train + test) for a drug based on RO-Crate paths.
        """
        test_data = os.path.join(test_rocrate_path, 'test_data.txt')
        test_count = self._count_lines(test_data)
        if test_count is None:
            return None

        train_rocrate_path = None
        if test_rocrate_path.endswith('_test_rocrate'):
            train_rocrate_path = test_rocrate_path.replace('_test_rocrate', '_train_rocrate')
        train_count = None
        if train_rocrate_path and os.path.isdir(train_rocrate_path):
            train_data = os.path.join(train_rocrate_path, 'train_data.txt')
            train_count = self._count_lines(train_data)
        if train_count is None:
            return test_count
        return test_count + train_count

    def _count_lines(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r') as f:
                return sum(1 for _ in f)
        except Exception:
            return None

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
            
            # Extract and save feature importance matrix for ElasticNet models
            self._extract_feature_importance(predict_rocrates_map, test_rocrates_map)

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
        """.format(version=aixport.__version__,
                   cmd=BenchmarkTool.COMMAND)

        parser = subparsers.add_parser(BenchmarkTool.COMMAND,
                                       help='Benchmarks predictions on trained models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)
        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')

        parser.add_argument('--input_test_rocrates',
                            help='File listing directories of test RO-Crates, one per line')
        parser.add_argument('--predictions_rocrate',
                            help='RO-Crate where prediction was run')

        return parser
