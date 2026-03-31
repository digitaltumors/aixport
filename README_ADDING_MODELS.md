# Adding Models and Reproducing Results

This guide explains how to add a new model to the aixport pipeline and how to reproduce the 4-model results we ran. The steps are short and designed to be easy to follow.

---

## 1) What "adding a model" means

Each model is a small Python package with a command-line entrypoint (a `*_drecmd.py` script). aixport calls these scripts to run train and predict steps.

To add a model, you need:

- A runner that reads a RO-Crate input folder and writes outputs to an output folder.
- A CLI script that supports `--input_crate`, `--mode train|test`, and any model hyperparameters.
- A package install step (`make install` or `pip install -e .`) so the command is on `PATH`.

The repo already follows this pattern for:
- `elasticnet_dre`
- `randomforest_dre`
- `xgboost_dre`
- `nest_vnn_dre` (NeST‑VNN wrapper)

---

## 1.1 From scratch: adding a new model (start to finish)

This is the full, end‑to‑end flow we followed for NeST‑VNN and the baseline models.

### Step A — Get the code

Clone or copy the model repo into your local `digitaltumors/` folder (example):

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors
git clone <MODEL_REPO_URL> mymodel_dre
```

If the code already exists elsewhere, you can copy it in instead of cloning.

### Step B — Add the DRE wrapper

Inside the model folder, create a small package named `mymodel_dre/` with:

- `__init__.py` (metadata)
- `exceptions.py`
- `runner.py` (train + predict logic)
- `mymodel_drecmd.py` (CLI entrypoint)

Minimum CLI requirements:
- `--input_crate`
- `--mode train|test`
- `--model` (for predict)
- optional: `--config` (so aixport can pass hyperparameters)

### Step C — Add packaging so it installs like the others

Add:
- `setup.py`
- `setup.cfg`
- `Makefile` (with `make install`)

Then install it:

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/mymodel_dre
make install
```

This makes `mymodel_drecmd.py` available on `PATH`.

### Step D — Add the model to the shared config

Edit:

```
/cellar/users/<YOUR_USERNAME>/digitaltumors/aixport/configs/aixport_models.json
```

Add a new entry:

```json
"mymodel_drecmd.py": {
  "config": {
    "train": { "param1": 1, "param2": 2 },
    "test": { "param1": 1 }
  }
}
```

### Step E — Reinstall aixport (so config wiring is picked up)

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/aixport
make install
```

### Step F — Run train + predict

Use the same commands as in Section 4, but include your model in the config JSON.

---

## 1.3 Publish your new model (push to GitHub)

After your model works locally, push it to your GitHub repo:

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/mymodel_dre
git status -sb
git add -A
git commit -m "Add mymodel DRE wrapper"
git push origin main
```

If your default branch is not `main`, replace it with the correct branch name.

## 1.2 Example: Adding NeST‑VNN to aixport

This is a concrete example using the NeST‑VNN wrapper we added.

### Step 1 — Copy or clone the model

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors
cp -R /cellar/users/<YOUR_USERNAME>/ideker_github_NeST_VNN/nest_vnn nest_vnn_dre
```

### Step 2 — Add the DRE wrapper

Inside `nest_vnn_dre/`, add:

```
nest_vnn_dre/
  nest_vnn_dre/
    __init__.py
    exceptions.py
    runner.py
    nest_vnn_drecmd.py
```

The CLI should accept `--input_crate`, `--mode`, `--model`, and `--config`.

### Step 3 — Add packaging and install

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/nest_vnn_dre
make install
```

### Step 4 — Register in the aixport config

Edit:

```
/cellar/users/<YOUR_USERNAME>/digitaltumors/aixport/configs/aixport_models.json
```

Add:

```json
"nest_vnn_drecmd.py": {
  "config": {
    "train": {
      "cuda": 0,
      "batchsize": 64,
      "epoch": 2,
      "genotype_hiddens": 4,
      "lr": 0.001,
      "wd": 0.001
    },
    "test": {
      "cuda": 0,
      "batchsize": 1000
    }
  }
}
```

### Step 5 — Reinstall aixport

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/aixport
make install
```

Now NeST‑VNN is available in the shared pipeline.

## 2) Input RO-Crate files (what they are)

Each drug has two RO-Crates:
- `*_train_rocrate`
- `*_test_rocrate`

**What is an RO‑Crate?**  
In this project, an RO‑Crate is just a folder that bundles all required inputs
for a model run. It looks like:

```
<DrugName>_train_rocrate/
  gene2ind.txt
  cell2ind.txt
  cell2mutation.txt
  cell2cndeletion.txt
  cell2cnamplification.txt
  train_data.txt
  ro-crate-metadata.json   (optional)
```

The test crate has the same structure but with `test_data.txt`.

Inside each RO-Crate, the core inputs are:

- `gene2ind.txt`  
  Mapping of gene index to gene name.
- `cell2ind.txt`  
  Mapping of cell index to cell name.
- `cell2mutation.txt`  
  Binary mutation matrix per cell (comma-delimited).
- `cell2cndeletion.txt`  
  Copy number deletion matrix per cell (comma-delimited).
- `cell2cnamplification.txt`  
  Copy number amplification matrix per cell (comma-delimited).
- `train_data.txt` (train rocrate only)  
  Tab-delimited samples used for training.
- `test_data.txt` (test rocrate only)  
  Tab-delimited samples used for evaluation.

NeST‑VNN additionally needs:
- `ontology.txt` (or `ontology.tsv`, `hierarchy.txt`, `hierarchy.cx2`)  
  Must be a 3-column, tab-delimited ontology file.

We use fallback NeST‑VNN inputs here:
`/cellar/users/abishai/ideker_github_NeST_VNN/nest_vnn/sample`

---

## 2.1 How the code consumes RO‑Crates (inputs → outputs)

Each `*_drecmd.py` command is a thin CLI around a runner. The runner:

1. **Reads an input RO‑Crate** (`--input_crate <path>`), which is just a folder of files.
2. **Trains or predicts** based on `--mode train|test`.
3. **Writes an output RO‑Crate** (a folder under `trainout/trainedmodels` or `predictout/predictions`).

Expected outputs:

- **Train** (`--mode train`):
  - `model.pkl` (or `model.pt`)
  - `train_predictions.txt`
  - task logs (`task_*_start.json`, `task_*_finish.json`)

- **Predict** (`--mode test`):
  - `test_predictions.txt`
  - task logs (`task_*_start.json`, `task_*_finish.json`)

aixport builds these output folders automatically and organizes them as:

```
trainout/trainedmodels/<Drug>_train_rocrate_<algorithm>/
predictout/predictions/<Drug>_test_rocrate_<algorithm>/
```

That structure is how the benchmark step finds and compares results.

---

## 3) One config file for all models

aixport supports a single JSON config to set hyperparameters for each model.

Config file:
`/cellar/users/abishai/digitaltumors/aixport/configs/aixport_models.json`

Inside it, each model name maps to its `train` and `test` settings.

Example (snippet):

```json
{
  "elasticnet_drecmd.py": {
    "config": {
      "train": {
        "alpha": 0.001,
        "l1_ratio": 0.5,
        "feature_types": ["mutations", "cnd", "cna", "expression"],
        "task_type": "regression",
        "label_threshold": 0.5
      }
    }
  }
}
```

When aixport runs, it writes per-model config files to:
`<outdir>/algorithm_configs/`

Feature/task config notes for the 3 baseline models:

- `feature_types` can be a list such as `["mutations", "cna", "cnd"]` or `["expression"]`
- `genomic_features` still works for legacy presets like `all` and `all4`
- `task_type` can be `regression` or `classification`
- `label_threshold` controls how continuous AUC values are binarized for classification
- `loss_function` is optional; `bce` is supported for ElasticNet and XGBoost classification modes

If you want `optimize-train` to search across multiple feature combinations, add:

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
      }
    }
  }
}
```

If you want binary classification instead of regression, use:

```json
{
  "elasticnet_drecmd.py": {
    "config": {
      "train": {
        "task_type": "classification",
        "label_threshold": 0.5,
        "loss_function": "bce",
        "feature_types": ["mutations", "cnd", "cna", "expression"]
      }
    }
  }
}
```

If you want an end-to-end reproducible example that runs
`optimize-train -> train -> predict -> benchmark` for the 3 classical models,
see `scripts/run_optimized_scenarios.sh`.

---

## 4) Reproduce the 4-model run (5 drugs)

This reproduces the exact 4-model run (elasticnet, randomforest, xgboost, nest_vnn) on the first 5 drugs.

### 4.1 Create environment (recommended)

NRNB GPU session example (adjust as needed):

```bash
srun --partition=nrnb-gpu --gres=gpu:a30:1 --pty bash
```

This allocates a GPU shell session on the cluster so NeST‑VNN can train.

Example (adjust name if needed):

```bash
conda env create -f /cellar/users/<YOUR_USERNAME>/digitaltumors/nest_vnn_dre/conda-envs/cuda11_env.yml
conda activate cuda11_env
```

This creates and activates the CUDA-enabled environment used for GPU training.

### 4.2 Install model packages

```bash
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/aixport && make install
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/elasticnet_dre && make install
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/randomforest_dre && make install
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/xgboost_dre && make install
cd /cellar/users/<YOUR_USERNAME>/digitaltumors/nest_vnn_dre && make install
```

This makes each model CLI available on `PATH` so aixport can call it.

### 4.3 Prepare input lists (5 train + matching test)

```bash
mkdir -p /cellar/users/<YOUR_USERNAME>/four_models_test

find /cellar/users/<YOUR_USERNAME>/rocrates/coder/combined -type d -name "*_train_rocrate" | sort | head -n 5 \
  > /cellar/users/<YOUR_USERNAME>/four_models_test/coder_train_input_rocrates.txt

awk -F/ '{print $NF}' /cellar/users/<YOUR_USERNAME>/four_models_test/coder_train_input_rocrates.txt \
  | sed 's/_train_rocrate$//' \
  | while read -r drug; do
      find /cellar/users/<YOUR_USERNAME>/rocrates/coder/combined -type d -name "${drug}_test_rocrate"
    done | sort \
  > /cellar/users/<YOUR_USERNAME>/four_models_test/coder_test_input_rocrates.txt
```

This picks **5 training RO‑Crates** and then finds the **matching test RO‑Crates**
for the same drugs, so train/predict runs on aligned pairs.

### 4.4 Train (GPU for NeST‑VNN)

```bash
export PATH=/cellar/users/<YOUR_USERNAME>/digitaltumors/nest_vnn_dre/nest_vnn_dre:$PATH
export NEST_VNN_CUDA=0
export NEST_VNN_INPUTS=/cellar/users/<YOUR_USERNAME>/ideker_github_NeST_VNN/nest_vnn/sample

aixportcmd.py train /cellar/users/<YOUR_USERNAME>/four_models_test/trainout \
  --input /cellar/users/<YOUR_USERNAME>/four_models_test/coder_train_input_rocrates.txt \
  --algorithms /cellar/users/<YOUR_USERNAME>/digitaltumors/aixport/configs/aixport_models.json \
  --run_mode bash

cd /cellar/users/<YOUR_USERNAME>/four_models_test/trainout
bash bash_train_job.sh
```

This builds the per-model train jobs and executes them.

### 4.5 Predict

```bash
aixportcmd.py predict /cellar/users/<YOUR_USERNAME>/four_models_test/predictout \
  --input /cellar/users/<YOUR_USERNAME>/four_models_test/coder_test_input_rocrates.txt \
  --trainedmodels /cellar/users/<YOUR_USERNAME>/four_models_test/trainout/trainedmodels \
  --algorithms /cellar/users/<YOUR_USERNAME>/digitaltumors/aixport/configs/aixport_models.json \
  --run_mode bash

cd /cellar/users/<YOUR_USERNAME>/four_models_test/predictout
bash bash_predict_job.sh
```

This runs predictions for each model using the trained model folders.

### 4.6 Benchmark

```bash
rm -rf /cellar/users/<YOUR_USERNAME>/four_models_test/benchmark

aixportcmd.py benchmark /cellar/users/<YOUR_USERNAME>/four_models_test/benchmark \
  --input_test_rocrates /cellar/users/<YOUR_USERNAME>/four_models_test/coder_test_input_rocrates.txt \
  --predictions_rocrate /cellar/users/<YOUR_USERNAME>/four_models_test/predictout
```

This scores each model’s predictions and produces the summary plots.

Outputs:
- `/cellar/users/<YOUR_USERNAME>/four_models_test/benchmark/results.csv`
- `/cellar/users/<YOUR_USERNAME>/four_models_test/benchmark/results.png`
- `/cellar/users/<YOUR_USERNAME>/four_models_test/benchmark/results.svg`

---

## 5) Adding another model (checklist)

1. Create a new package folder (example: `mynewmodel_dre/`)
2. Implement `runner.py` with `--input_crate` + `--mode`.
3. Implement `mynewmodel_drecmd.py` CLI.
4. Add `setup.py` + `Makefile` for `make install`.
5. Add the model to `aixport/configs/aixport_models.json`:
   - new top-level key for your model
   - set `train` and `test` hyperparameters
6. Re-run `make install`, then train/predict as above.

---

## 6) Quick troubleshooting

- **"command not found"**  
  Run `make install` in the model folder to add the CLI to PATH.

- **NeST‑VNN ontology errors**  
  Ensure `ontology.txt` is in your RO-Crate or set `NEST_VNN_INPUTS` to a folder that contains it.

- **NaN correlations in benchmark**  
  This happens if predictions are constant (zero variance). It’s not a crash—just a stats edge case.
