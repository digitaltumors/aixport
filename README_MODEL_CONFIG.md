# Model Config Guide

This guide covers the config parameters used by the 3 classical AIxPORT baseline
models:

- `elasticnet_drecmd.py`
- `randomforest_drecmd.py`
- `xgboost_drecmd.py`

It focuses on:

- which parameters to change for each modeling condition
- how to switch feature sets, including expression
- how to run regression versus classification
- how to let `optimize-train` search over feature combinations

This does not cover `nest_vnn_drecmd.py`.

## 1. Config shape

The shared config file lives at:

`/cellar/users/abishai/digitaltumors/aixport/configs/aixport_models.json`

Each algorithm has a `train` block and a `test` block.

Example:

```json
{
  "elasticnet_drecmd.py": {
    "config": {
      "train": {
        "alpha": 0.001,
        "l1_ratio": 0.5,
        "feature_types": ["mutations", "cnd", "cna"],
        "task_type": "regression",
        "label_threshold": 0.5,
        "loss_function": null
      },
      "test": {}
    }
  }
}
```

## 2. Preferred feature config

Use `feature_types` for new runs.

Supported feature names:

- `mutations`
- `cna`
- `cnd`
- `fusion`
- `expression`

Examples:

- `["mutations", "cnd", "cna"]`: current baseline feature set
- `["mutations", "cnd", "cna", "expression"]`: add expression to the baseline
- `["expression"]`: expression-only model
- `["mutations", "expression"]`: mutation + expression only

Legacy support:

- `genomic_features: "all"` means `["mutations", "cnd", "cna"]`
- `genomic_features: "all4"` means `["mutations", "cnd", "cna", "expression"]`

Use `feature_types` instead of `genomic_features` unless you need backward compatibility.

## 3. Which parameters to change for which condition

### Standard regression baseline

Use this when you want the existing drug-response setup with continuous AUC prediction.

Change:

- `task_type: "regression"`
- `feature_types: ["mutations", "cnd", "cna"]`

Example:

```json
{
  "xgboost_drecmd.py": {
    "config": {
      "train": {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.1,
        "feature_types": ["mutations", "cnd", "cna"],
        "task_type": "regression"
      },
      "test": {}
    }
  }
}
```

### Add expression to the baseline

Use this when you want to test whether expression improves predictive performance.

Change:

- `feature_types: ["mutations", "cnd", "cna", "expression"]`

Example:

```json
{
  "randomforest_drecmd.py": {
    "config": {
      "train": {
        "n_estimators": 500,
        "max_features": "sqrt",
        "feature_types": ["mutations", "cnd", "cna", "expression"],
        "task_type": "regression"
      },
      "test": {}
    }
  }
}
```

### Expression-only experiment

Use this when you want to isolate the contribution of gene expression alone.

Change:

- `feature_types: ["expression"]`

### Binary classification instead of regression

Use this when you want to predict sensitive/resistant labels instead of continuous AUC.

Change:

- `task_type: "classification"`
- `label_threshold: 0.5` or another cutoff

Interpretation:

- samples with `AUC >= label_threshold` are assigned label `1`
- samples with `AUC < label_threshold` are assigned label `0`

Example:

```json
{
  "elasticnet_drecmd.py": {
    "config": {
      "train": {
        "alpha": 0.001,
        "l1_ratio": 0.5,
        "feature_types": ["mutations", "cnd", "cna", "expression"],
        "task_type": "classification",
        "label_threshold": 0.5,
        "loss_function": "bce"
      },
      "test": {}
    }
  }
}
```

### Change the classification threshold

Use this when you want a stricter or looser sensitive/resistant definition.

Change:

- `label_threshold`

Examples:

- `0.5`: default split
- `0.4`: more samples become positive
- `0.6`: fewer samples become positive

Important:

- if the threshold collapses all training examples into one class, training will fail
- for classification CV, the optimizer also needs at least 2 examples from each class in each fold

## 4. Loss and objective settings

### ElasticNet

Regression:

- uses `ElasticNet`
- `loss_function` is not used

Classification:

- uses `SGDClassifier` with elastic-net penalty
- set `loss_function: "bce"` for logistic / binary cross-entropy style training

Recommended classification config:

```json
{
  "task_type": "classification",
  "label_threshold": 0.5,
  "loss_function": "bce"
}
```

### RandomForest

Regression:

- uses `RandomForestRegressor`

Classification:

- uses `RandomForestClassifier`

Note:

- `loss_function` is accepted in config for consistency, but RandomForest does not use a BCE-style loss parameter

### XGBoost

Regression:

- uses `XGBRegressor(objective="reg:squarederror")`

Classification:

- uses `XGBClassifier`
- set `loss_function: "bce"` to use binary logistic classification

Recommended classification config:

```json
{
  "task_type": "classification",
  "label_threshold": 0.5,
  "loss_function": "bce"
}
```

## 5. Model-specific hyperparameters

### ElasticNet

Main parameters:

- `alpha`
- `l1_ratio`
- `max_iter`

When to change them:

- increase `alpha` if the model is too noisy or overfitting
- adjust `l1_ratio` toward `1.0` for more sparsity
- increase `max_iter` if optimization fails to converge

### RandomForest

Main parameters:

- `n_estimators`
- `max_depth`
- `max_features`
- `n_jobs`

When to change them:

- increase `n_estimators` for more stable trees
- lower `max_depth` to regularize
- change `max_features` to control split diversity

### XGBoost

Main parameters:

- `n_estimators`
- `max_depth`
- `learning_rate`
- `subsample`
- `colsample_bytree`

When to change them:

- lower `learning_rate` and increase `n_estimators` for smoother fitting
- lower `subsample` or `colsample_bytree` to regularize
- lower `max_depth` if the model is too aggressive

## 6. Using optimize-train to compare feature combinations

If you want `aixportcmd.py optimize-train` to test multiple feature combinations,
use `feature_set_search` in the `train` block.

Example:

```json
{
  "xgboost_drecmd.py": {
    "config": {
      "train": {
        "task_type": "regression",
        "feature_set_search": [
          ["mutations", "cnd", "cna"],
          ["mutations", "cnd", "cna", "expression"],
          ["expression"]
        ]
      },
      "test": {}
    }
  }
}
```

`optimize-train` also supports:

- `genomic_features_search`: legacy preset search like `["all", "all4"]`
- `label_threshold_search`: try multiple classification thresholds
- `loss_search_space`: try multiple classification losses/objectives where supported

Example:

```json
{
  "elasticnet_drecmd.py": {
    "config": {
      "train": {
        "task_type": "classification",
        "label_threshold_search": [0.4, 0.5, 0.6],
        "loss_search_space": ["bce"],
        "feature_set_search": [
          ["mutations", "cnd", "cna"],
          ["mutations", "cnd", "cna", "expression"]
        ]
      },
      "test": {}
    }
  }
}
```

## 7. What optimize-train scores

Regression:

- cross-validated Pearson correlation

Classification:

- cross-validated ROC AUC

This means:

- use regression when your target is continuous drug response
- use classification when you explicitly want binary response groups

## 8. Quick recipes

### Current default baseline

```json
{
  "feature_types": ["mutations", "cnd", "cna"],
  "task_type": "regression"
}
```

### Baseline + expression

```json
{
  "feature_types": ["mutations", "cnd", "cna", "expression"],
  "task_type": "regression"
}
```

### Expression-only baseline

```json
{
  "feature_types": ["expression"],
  "task_type": "regression"
}
```

### Binary classifier

```json
{
  "feature_types": ["mutations", "cnd", "cna", "expression"],
  "task_type": "classification",
  "label_threshold": 0.5,
  "loss_function": "bce"
}
```

## 9. Practical advice

- Prefer `feature_types` over `genomic_features` for new work
- Keep `task_type: "regression"` unless you explicitly want binary labels
- Only use `loss_function: "bce"` when running ElasticNet or XGBoost classification
- Start with `label_threshold: 0.5` unless you have a reason to shift the class boundary
- Use `feature_set_search` in `optimize-train` if you want the data to decide whether expression helps
