import copy
import itertools
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold

import aixport
from aixport.basecmdtool import BaseCommandLineTool
from aixport.exceptions import AIxPORTError
import cellmaps_utils.constants


def _pearson_corr(y_true, y_pred):
    if y_true is None or y_pred is None:
        return -1.0
    if len(y_true) < 2:
        return -1.0
    if np.std(y_true) == 0 or np.std(y_pred) == 0:
        return -1.0
    corr = np.corrcoef(y_true, y_pred)[0, 1]
    if np.isnan(corr):
        return -1.0
    return float(corr)


FEATURE_PRESETS = {
    'all': ['mutations', 'cnd', 'cna'],
    'all4': ['mutations', 'cnd', 'cna', 'expression'],
    'mutations': ['mutations'],
    'mutation': ['mutations'],
    'mut': ['mutations'],
    'cna': ['cna'],
    'amplification': ['cna'],
    'amplifications': ['cna'],
    'amp': ['cna'],
    'cnd': ['cnd'],
    'deletion': ['cnd'],
    'deletions': ['cnd'],
    'del': ['cnd'],
    'fusion': ['fusion'],
    'fusions': ['fusion'],
    'expression': ['expression'],
    'expr': ['expression']
}
FEATURE_FILES = {
    'mutations': 'cell2mutation.txt',
    'cnd': 'cell2cndeletion.txt',
    'cna': 'cell2cnamplification.txt',
    'fusion': 'cell2fusion.txt',
    'expression': 'cell2expression.txt'
}
ELASTICNET_CLASSIFICATION_LOSSES = {
    'bce': 'log_loss',
    'binary_crossentropy': 'log_loss',
    'binary_cross_entropy': 'log_loss',
    'logloss': 'log_loss',
    'log_loss': 'log_loss'
}
XGBOOST_CLASSIFICATION_OBJECTIVES = {
    'bce': 'binary:logistic',
    'binary_crossentropy': 'binary:logistic',
    'binary_cross_entropy': 'binary:logistic',
    'binary:logistic': 'binary:logistic',
    'logloss': 'binary:logistic',
    'log_loss': 'binary:logistic'
}


def _extend_feature_tokens(value, resolved):
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _extend_feature_tokens(item, resolved)
        return

    text = str(value).strip()
    if not text:
        return

    lower_text = text.lower()
    if lower_text in FEATURE_PRESETS:
        for token in FEATURE_PRESETS[lower_text]:
            if token not in resolved:
                resolved.append(token)
        return

    for part in [p for p in re.split(r'[\s,;+|]+', lower_text) if p]:
        if part not in FEATURE_PRESETS:
            raise AIxPORTError('Unsupported feature token: {}'.format(part))
        for token in FEATURE_PRESETS[part]:
            if token not in resolved:
                resolved.append(token)


def _resolve_feature_types(feature_types=None, genomic_features='all'):
    resolved = []
    source = feature_types if feature_types not in (None, '') else genomic_features
    _extend_feature_tokens(source, resolved)
    if len(resolved) == 0:
        raise AIxPORTError('No genomic feature types were selected')
    return resolved


def _resolve_task_type(task_type):
    normalized = str(task_type or 'regression').strip().lower()
    if normalized not in ('regression', 'classification'):
        raise AIxPORTError('Unsupported task_type: {}'.format(task_type))
    return normalized


def _build_target(values, task_type, label_threshold):
    y = np.asarray(values, dtype=float)
    if task_type == 'regression':
        return y
    labels = (y >= float(label_threshold)).astype(int)
    if np.unique(labels).size < 2:
        raise AIxPORTError('Classification labels collapse to a single class; adjust label_threshold')
    return labels


def _classification_score(y_true, y_pred):
    if y_true is None or y_pred is None:
        return -1.0
    if len(y_true) < 2 or np.unique(y_true).size < 2:
        return -1.0
    try:
        score = roc_auc_score(y_true, y_pred)
    except Exception:
        return -1.0
    if np.isnan(score):
        return -1.0
    return float(score)


class OptimizeTrainTool(BaseCommandLineTool):
    """
    Performs per-RO-Crate hyperparameter optimization and writes an algorithms
    JSON consumable by aixport train/predict.
    """
    COMMAND = 'optimize-train'

    def __init__(self, theargs, provenance_utils=None):
        super().__init__(theargs,
                         provenance_utils=provenance_utils)

    def _get_training_rocrates(self, input_file):
        with open(input_file, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped == '':
                    continue
                yield os.path.abspath(stripped)

    def _parse_algorithms_argument(self):
        algorithms_arg = self._theargs.get('algorithms')
        if algorithms_arg is None:
            return {}, []

        if os.path.isfile(algorithms_arg):
            try:
                with open(algorithms_arg, 'r') as f:
                    algorithms_data = json.load(f)
            except (OSError, json.JSONDecodeError) as ex:
                raise AIxPORTError('Unable to load algorithms configuration file: ' +
                                   str(ex))
            if not isinstance(algorithms_data, dict):
                raise AIxPORTError('Algorithms configuration file must be a JSON object')
            return algorithms_data, list(algorithms_data.keys())

        algorithms = [algo for algo in re.split(r'\s*,\s*', str(algorithms_arg)) if algo]
        algorithms_data = {algo: {'config': ''} for algo in algorithms}
        return algorithms_data, algorithms

    def _load_rocrate_xy(self, crate_dir, genomic_features='all',
                         feature_types=None, task_type='regression',
                         label_threshold=0.5):
        file_paths = {
            'gene2ind.txt': os.path.join(crate_dir, 'gene2ind.txt'),
            'cell2ind.txt': os.path.join(crate_dir, 'cell2ind.txt'),
            'cell2mutation.txt': os.path.join(crate_dir, 'cell2mutation.txt'),
            'cell2cndeletion.txt': os.path.join(crate_dir, 'cell2cndeletion.txt'),
            'cell2cnamplification.txt': os.path.join(crate_dir, 'cell2cnamplification.txt'),
            'cell2fusion.txt': os.path.join(crate_dir, 'cell2fusion.txt'),
            'cell2expression.txt': os.path.join(crate_dir, 'cell2expression.txt'),
            'train_data.txt': os.path.join(crate_dir, 'train_data.txt'),
        }
        selected_feature_types = _resolve_feature_types(feature_types=feature_types,
                                                        genomic_features=genomic_features)
        task_type = _resolve_task_type(task_type)
        required_files = ['gene2ind.txt', 'cell2ind.txt', 'train_data.txt']
        for feature_type in selected_feature_types:
            required_files.append(FEATURE_FILES[feature_type])

        missing = [fname for fname in required_files if not os.path.exists(file_paths[fname])]
        if missing:
            raise AIxPORTError('Missing required files in {}: {}'.format(crate_dir, ','.join(missing)))

        gene_index = pd.read_csv(file_paths['gene2ind.txt'], sep='\t', header=None, names=['I', 'G'])
        gene_list = gene_index['G']
        cell_index = pd.read_csv(file_paths['cell2ind.txt'], sep='\t', header=None, names=['I', 'C'])
        cell_map = dict(zip(cell_index['C'], cell_index['I']))
        train_df = pd.read_csv(file_paths['train_data.txt'], sep='\t', header=None,
                               names=['cell', 'smiles', 'auc', 'dataset'])

        feature_arrays = []
        for feature_type in selected_feature_types:
            feature_df = pd.read_csv(file_paths[FEATURE_FILES[feature_type]], header=None, names=gene_list)
            feature_arrays.append(feature_df.values)
        if not feature_arrays:
            raise AIxPORTError('No feature arrays loaded for feature_types={}'.format(selected_feature_types))

        cell_features = np.concatenate(feature_arrays, axis=1)

        indices = []
        auc_values = []
        cells = []
        for _, row in train_df.iterrows():
            cell = row['cell']
            if cell not in cell_map:
                continue
            indices.append(int(cell_map[cell]))
            auc_values.append(float(row['auc']))
            cells.append(cell)
        if len(indices) < 4:
            raise AIxPORTError('Not enough mapped rows in train_data.txt for {}'.format(crate_dir))

        x = cell_features[np.array(indices)]
        y = _build_target(auc_values, task_type=task_type, label_threshold=label_threshold)
        return x, y, np.array(cells)

    @staticmethod
    def _grid_dict_to_param_list(grid_dict):
        keys = list(grid_dict.keys())
        values = [grid_dict[k] for k in keys]
        params = []
        for combo in itertools.product(*values):
            params.append(dict(zip(keys, combo)))
        return params

    def _get_search_space(self, algo_key, base_train_config):
        preset = self._theargs.get('preset', 'fast')
        if base_train_config is None:
            base_train_config = {}
        task_type = _resolve_task_type(base_train_config.get('task_type', 'regression'))

        if algo_key == 'elasticnet_drecmd.py':
            if preset == 'standard':
                grid = {
                    'alpha': [1e-4, 1e-3, 1e-2, 1e-1, 1.0],
                    'l1_ratio': [0.1, 0.3, 0.5, 0.7, 0.9],
                }
            else:
                grid = {
                    'alpha': [1e-3, 1e-2, 1e-1],
                    'l1_ratio': [0.3, 0.5, 0.7],
                }
        elif algo_key == 'randomforest_drecmd.py':
            if preset == 'standard':
                grid = {
                    'n_estimators': [200, 500, 800],
                    'max_depth': [None, 10, 20],
                    'max_features': ['sqrt', 0.5],
                }
            else:
                grid = {
                    'n_estimators': [200, 500],
                    'max_depth': [None, 12],
                    'max_features': ['sqrt', 0.5],
                }
        elif algo_key == 'xgboost_drecmd.py':
            if preset == 'standard':
                grid = {
                    'n_estimators': [200, 500],
                    'max_depth': [4, 6, 8],
                    'learning_rate': [0.03, 0.1],
                    'subsample': [0.8, 1.0],
                    'colsample_bytree': [0.8, 1.0],
                }
            else:
                grid = {
                    'n_estimators': [200, 500],
                    'max_depth': [4, 6],
                    'learning_rate': [0.05, 0.1],
                    'subsample': [0.8, 1.0],
                    'colsample_bytree': [0.8, 1.0],
                }
        else:
            return []

        # ensure existing default values are also considered
        for key in list(grid.keys()):
            if key in base_train_config:
                val = base_train_config.get(key)
                if val not in grid[key]:
                    grid[key] = [val] + list(grid[key])

        if 'feature_set_search' in base_train_config:
            grid['feature_types'] = list(base_train_config.get('feature_set_search') or [])
        elif 'feature_types' in base_train_config:
            grid['feature_types'] = [base_train_config.get('feature_types')]
        elif 'genomic_features_search' in base_train_config:
            grid['genomic_features'] = list(base_train_config.get('genomic_features_search') or [])
        elif 'genomic_features' in base_train_config:
            grid['genomic_features'] = [base_train_config.get('genomic_features')]

        if 'task_type' in base_train_config:
            grid['task_type'] = [task_type]

        if task_type == 'classification':
            if 'label_threshold_search' in base_train_config:
                grid['label_threshold'] = list(base_train_config.get('label_threshold_search') or [])
            else:
                grid['label_threshold'] = [float(base_train_config.get('label_threshold', 0.5))]

            if algo_key == 'elasticnet_drecmd.py':
                if 'loss_search_space' in base_train_config:
                    grid['loss_function'] = list(base_train_config.get('loss_search_space') or [])
                else:
                    grid['loss_function'] = [base_train_config.get('loss_function', 'bce')]
            elif algo_key == 'xgboost_drecmd.py':
                if 'loss_search_space' in base_train_config:
                    grid['loss_function'] = list(base_train_config.get('loss_search_space') or [])
                else:
                    grid['loss_function'] = [base_train_config.get('loss_function', 'bce')]

        param_list = self._grid_dict_to_param_list(grid)
        max_combos = int(self._theargs.get('max_combos', 24))
        if max_combos > 0 and len(param_list) > max_combos:
            param_list = param_list[:max_combos]
        return param_list

    @staticmethod
    def _build_model(algo_key, params, random_state=42):
        task_type = _resolve_task_type(params.get('task_type', 'regression'))
        if algo_key == 'elasticnet_drecmd.py':
            if task_type == 'classification':
                from sklearn.linear_model import SGDClassifier
                loss_function = str(params.get('loss_function', 'bce')).strip().lower().replace('-', '_')
                loss_function = ELASTICNET_CLASSIFICATION_LOSSES.get(loss_function)
                if loss_function is None:
                    raise AIxPORTError('Unsupported ElasticNet classification loss_function: {}'.format(
                        params.get('loss_function')))
                return SGDClassifier(loss=loss_function,
                                     penalty='elasticnet',
                                     alpha=float(params['alpha']),
                                     l1_ratio=float(params['l1_ratio']),
                                     max_iter=int(params.get('max_iter', 1000)),
                                     random_state=random_state)
            from sklearn.linear_model import ElasticNet
            return ElasticNet(alpha=float(params['alpha']),
                              l1_ratio=float(params['l1_ratio']),
                              max_iter=int(params.get('max_iter', 1000)),
                              random_state=random_state)
        if algo_key == 'randomforest_drecmd.py':
            if task_type == 'classification':
                from sklearn.ensemble import RandomForestClassifier
                return RandomForestClassifier(n_estimators=int(params['n_estimators']),
                                              max_depth=params.get('max_depth', None),
                                              max_features=params.get('max_features', 'sqrt'),
                                              random_state=random_state,
                                              n_jobs=int(params.get('n_jobs', -1)))
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(n_estimators=int(params['n_estimators']),
                                         max_depth=params.get('max_depth', None),
                                         max_features=params.get('max_features', 'sqrt'),
                                         random_state=random_state,
                                         n_jobs=int(params.get('n_jobs', -1)))
        if algo_key == 'xgboost_drecmd.py':
            if task_type == 'classification':
                from xgboost import XGBClassifier
                loss_function = str(params.get('loss_function', 'bce')).strip().lower().replace('-', '_')
                objective = XGBOOST_CLASSIFICATION_OBJECTIVES.get(loss_function)
                if objective is None:
                    raise AIxPORTError('Unsupported XGBoost classification loss_function: {}'.format(
                        params.get('loss_function')))
                return XGBClassifier(n_estimators=int(params['n_estimators']),
                                     max_depth=int(params['max_depth']),
                                     learning_rate=float(params['learning_rate']),
                                     subsample=float(params['subsample']),
                                     colsample_bytree=float(params['colsample_bytree']),
                                     random_state=random_state,
                                     objective=objective,
                                     eval_metric='logloss')
            from xgboost import XGBRegressor
            return XGBRegressor(n_estimators=int(params['n_estimators']),
                                max_depth=int(params['max_depth']),
                                learning_rate=float(params['learning_rate']),
                                subsample=float(params['subsample']),
                                colsample_bytree=float(params['colsample_bytree']),
                                random_state=random_state,
                                objective='reg:squarederror')
        raise AIxPORTError('Unsupported algorithm for optimization: {}'.format(algo_key))

    @staticmethod
    def _predict_scores(model, x, task_type):
        if task_type == 'classification':
            if hasattr(model, 'predict_proba'):
                return model.predict_proba(x)[:, 1]
            if hasattr(model, 'decision_function'):
                raw_scores = np.asarray(model.decision_function(x), dtype=float)
                return 1.0 / (1.0 + np.exp(-raw_scores))
            raise AIxPORTError('Classification model does not expose predict_proba or decision_function')
        return model.predict(x)

    @staticmethod
    def _score_predictions(y_true, y_pred, task_type):
        if task_type == 'classification':
            return _classification_score(y_true, y_pred)
        return _pearson_corr(y_true, y_pred)

    @staticmethod
    def _print_progress(prefix, current, total):
        if total <= 0:
            return
        width = 28
        filled = int((current * width) / total)
        if filled < 0:
            filled = 0
        if filled > width:
            filled = width
        bar = ('#' * filled) + ('-' * (width - filled))
        sys.stdout.write('\r{} [{}] {}/{}'.format(prefix, bar, current, total))
        sys.stdout.flush()
        if current >= total:
            sys.stdout.write('\n')
            sys.stdout.flush()

    def _find_best_params(self, algo_key, rocrate, base_train_config, candidates, progress_prefix=''):
        cv_folds = int(self._theargs.get('cv_folds', 3))
        random_state = int(self._theargs.get('random_state', 42))
        best_score = -np.inf
        best_params = None
        total = len(candidates)
        dataset_cache = {}
        for idx, candidate in enumerate(candidates, start=1):
            fold_scores = []
            try:
                candidate_config = copy.deepcopy(base_train_config or {})
                candidate_config.update(candidate)
                task_type = _resolve_task_type(candidate_config.get('task_type', 'regression'))
                label_threshold = float(candidate_config.get('label_threshold', 0.5))
                feature_types = _resolve_feature_types(feature_types=candidate_config.get('feature_types'),
                                                       genomic_features=candidate_config.get('genomic_features', 'all'))
                cache_key = (tuple(feature_types), task_type, label_threshold)
                if cache_key not in dataset_cache:
                    dataset_cache[cache_key] = self._load_rocrate_xy(
                        rocrate,
                        genomic_features=candidate_config.get('genomic_features', 'all'),
                        feature_types=candidate_config.get('feature_types'),
                        task_type=task_type,
                        label_threshold=label_threshold
                    )
                x, y, _cells = dataset_cache[cache_key]
                if task_type == 'classification':
                    class_counts = np.bincount(y.astype(int))
                    positive_counts = class_counts[class_counts > 0]
                    if len(positive_counts) < 2:
                        raise AIxPORTError('Classification labels do not contain both classes')
                    n_splits = min(cv_folds, int(np.min(positive_counts)))
                    if n_splits < 2:
                        raise AIxPORTError('Not enough per-class samples for CV ({} samples)'.format(len(y)))
                    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
                else:
                    n_splits = min(cv_folds, len(y))
                    if n_splits < 2:
                        raise AIxPORTError('Not enough samples for CV ({} samples)'.format(len(y)))
                    splitter = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
                for train_idx, val_idx in splitter.split(x, y):
                    model = self._build_model(algo_key, candidate_config, random_state=random_state)
                    model.fit(x[train_idx], y[train_idx])
                    pred = self._predict_scores(model, x[val_idx], task_type)
                    fold_scores.append(self._score_predictions(y[val_idx], pred, task_type))
                avg_score = float(np.mean(fold_scores))
            except Exception:
                avg_score = -np.inf
            if avg_score > best_score:
                best_score = avg_score
                best_params = candidate
            if progress_prefix:
                self._print_progress(progress_prefix, idx, total)

        if best_params is None:
            raise AIxPORTError('Failed to optimize {}'.format(algo_key))
        return best_params, best_score

    def run(self):
        exitcode = 99
        try:
            self._initialize_rocrate()

            if not os.path.isfile(self._theargs['input']):
                raise AIxPORTError('--input must be a file containing train RO-Crate paths')
            train_rocrates = list(self._get_training_rocrates(self._theargs['input']))
            if len(train_rocrates) == 0:
                raise AIxPORTError('No train RO-Crates found in input file')

            algorithms_data, algorithm_order = self._parse_algorithms_argument()
            if len(algorithm_order) == 0:
                raise AIxPORTError('No algorithms specified')

            summary_rows = []
            optimized_algorithms = {}
            nest_optimize_mode = self._theargs.get('nest_optimize_mode')
            random_state = int(self._theargs.get('random_state', 42))

            for algo in algorithm_order:
                print('[optimize-train] Algorithm: {}'.format(algo), flush=True)
                algo_settings = algorithms_data.get(algo, {})
                base_config = ''
                if isinstance(algo_settings, dict):
                    base_config = algo_settings.get('config', '')
                elif algo_settings is None:
                    base_config = ''
                else:
                    raise AIxPORTError('Configuration for algorithm {} must be object/null'.format(algo))

                if base_config is None:
                    base_config = ''
                if not isinstance(base_config, (dict, str)):
                    raise AIxPORTError('config for algorithm {} must be object/string/null'.format(algo))

                config_by_rocrate = {}
                algo_key = os.path.basename(str(algo))

                for rocrate in train_rocrates:
                    rocrate_cfg = None
                    status = 'optimized'
                    score = ''
                    notes = ''
                    rocrate_name = os.path.basename(rocrate)

                    if algo_key in ('elasticnet_drecmd.py', 'randomforest_drecmd.py', 'xgboost_drecmd.py'):
                        base_train_cfg = {}
                        base_test_cfg = {}
                        if isinstance(base_config, dict):
                            base_train_cfg = copy.deepcopy(base_config.get('train', {}))
                            base_test_cfg = copy.deepcopy(base_config.get('test', {}))
                        candidates = self._get_search_space(algo_key, base_train_cfg)
                        if len(candidates) == 0:
                            raise AIxPORTError('No candidate hyperparameters for {}'.format(algo_key))
                        prefix = '  {} {}'.format(algo_key.replace('_drecmd.py', ''), rocrate_name)
                        best_params, best_score = self._find_best_params(algo_key, rocrate, base_train_cfg, candidates,
                                                                         progress_prefix=prefix)
                        tuned_train_cfg = copy.deepcopy(base_train_cfg)
                        for transient_key in ('feature_set_search', 'genomic_features_search',
                                              'loss_search_space', 'label_threshold_search'):
                            tuned_train_cfg.pop(transient_key, None)
                        tuned_train_cfg.update(best_params)
                        if 'random_state' in tuned_train_cfg:
                            tuned_train_cfg['random_state'] = random_state
                        rocrate_cfg = {'train': tuned_train_cfg}
                        if isinstance(base_test_cfg, dict):
                            rocrate_cfg['test'] = base_test_cfg
                        score = '{:.6f}'.format(best_score)
                        print('  done {} best_cv={}'.format(rocrate_name, score), flush=True)
                    elif algo_key == 'nest_vnn_drecmd.py':
                        status = 'delegated'
                        notes = 'uses nest_vnn internal optimize mode during train'
                        if isinstance(base_config, dict):
                            rocrate_cfg = copy.deepcopy(base_config)
                        else:
                            rocrate_cfg = {'train': {}, 'test': {}}
                        if nest_optimize_mode is not None:
                            train_cfg = rocrate_cfg.setdefault('train', {})
                            train_cfg['optimize'] = int(nest_optimize_mode)
                    else:
                        status = 'skipped'
                        notes = 'unsupported algorithm for optimizer'
                        rocrate_cfg = None

                    if rocrate_cfg is not None:
                        config_by_rocrate[os.path.abspath(rocrate)] = rocrate_cfg

                    summary_rows.append({
                        'algorithm': algo,
                        'rocrate': os.path.abspath(rocrate),
                        'status': status,
                        'cv_score': score,
                        'notes': notes
                    })

                optimized_algorithms[algo] = {
                    'config': base_config,
                    'config_by_rocrate': config_by_rocrate
                }
                print('[optimize-train] Finished algorithm: {}'.format(algo), flush=True)

            optimized_path = os.path.join(self._theargs['outdir'], 'optimized_algorithms.json')
            with open(optimized_path, 'w') as f:
                json.dump(optimized_algorithms, f, indent=2, sort_keys=True)

            summary_path = os.path.join(self._theargs['outdir'], 'optimization_summary.tsv')
            with open(summary_path, 'w') as f:
                f.write('algorithm\trocrate\tstatus\tcv_score\tnotes\n')
                for row in summary_rows:
                    f.write('{algorithm}\t{rocrate}\t{status}\t{cv_score}\t{notes}\n'.format(**row))

            exitcode = 0
            self._finalize_rocrate()
            return exitcode
        finally:
            self._write_task_finish_json(exitcode)

    @staticmethod
    def add_subparser(subparsers):
        desc = """

        Version {version}

        {cmd} tunes hyperparameters on training RO-Crates and writes
        optimized_algorithms.json for aixport train/predict commands.
        The train config may include feature_set_search, genomic_features_search,
        label_threshold_search, and loss_search_space for the 3 classical models.
        """.format(version=aixport.__version__,
                   cmd=OptimizeTrainTool.COMMAND)

        parser = subparsers.add_parser(OptimizeTrainTool.COMMAND,
                                       help='Optimize hyperparameters per train RO-Crate',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')
        parser.add_argument('--input', required=True,
                            help='File containing absolute paths to training RO-Crate directories')
        parser.add_argument('--algorithms', default='elasticnet_drecmd.py',
                            help='Comma delimited list of algorithms or JSON config file')
        parser.add_argument('--cv_folds', type=int, default=3,
                            help='Cross-validation folds used during optimization')
        parser.add_argument('--preset', choices=['fast', 'standard'], default='fast',
                            help='Search-space size preset')
        parser.add_argument('--max_combos', type=int, default=24,
                            help='Maximum parameter combinations to evaluate per algorithm/drug')
        parser.add_argument('--random_state', type=int, default=42,
                            help='Random seed')
        parser.add_argument('--nest_optimize_mode', type=int, default=2,
                            help='Value to set for nest_vnn train.optimize in per-rocrate configs')
        return parser
