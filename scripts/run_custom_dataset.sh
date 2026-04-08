#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_custom_dataset.sh \
    --response-table /path/to/responses.tsv \
    --shared-features-dir /path/to/shared_features \
    --output-dir /path/to/output \
    [--model-config /path/to/custom_dataset_models.json] \
    [--drug-col drug] \
    [--cell-col cell_line] \
    [--group-col cell_line] \
    [--label-col auc] \
    [--smiles-col smiles] \
    [--dataset-col dataset] \
    [--dataset-default custom] \
    [--test-fraction 0.2] \
    [--seed 42] \
    [--min-rows-per-drug 20] \
    [--min-groups-per-drug 10] \
    [--drugs drug1,drug2] \
    [--label-transform none|log2] \
    [--log2-offset 1.0] \
    [--run-hpo auto|true|false] \
    [--skip-benchmark] \
    [--skip-install]

This script runs a custom dataset end-to-end:
  1. Build per-drug train/test RO-Crates from a response table
  2. Optionally run hyperparameter optimization
  3. Train enabled models
  4. Predict on held-out test RO-Crates
  5. Benchmark predictions

Model config JSON:
  - Add/remove models by editing the JSON file
  - Set "enabled": false to skip a model
  - Set "optimize": true/false to control per-model optimization when --run-hpo=auto
  - Add "install_path" for custom models that need pip install -e <repo>

Built-in defaults:
  - elasticnet_drecmd.py, randomforest_drecmd.py, xgboost_drecmd.py default to optimize=true
  - other models default to optimize=false unless set explicitly

Notes:
  - By default, the script expects the repos to live side-by-side:
      <workspace>/aixport
      <workspace>/elasticnet_dre
      <workspace>/randomforest_dre
      <workspace>/xgboost_dre
      <workspace>/nest_vnn_dre
  - Override repo locations with:
      AIXPORT_REPO
      ELASTICNET_REPO
      RANDOMFOREST_REPO
      XGBOOST_REPO
      NEST_VNN_REPO
  - Override Python with PYTHON_BIN=/path/to/python
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIXPORT_REPO="${AIXPORT_REPO:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "${AIXPORT_REPO}/.." && pwd)}"
ELASTICNET_REPO="${ELASTICNET_REPO:-${WORKSPACE_ROOT}/elasticnet_dre}"
RANDOMFOREST_REPO="${RANDOMFOREST_REPO:-${WORKSPACE_ROOT}/randomforest_dre}"
XGBOOST_REPO="${XGBOOST_REPO:-${WORKSPACE_ROOT}/xgboost_dre}"
NEST_VNN_REPO="${NEST_VNN_REPO:-${WORKSPACE_ROOT}/nest_vnn_dre}"
PYTHON_BIN="${PYTHON_BIN:-python}"

abs_path() {
  "${PYTHON_BIN}" - "$1" <<'PY'
import os
import sys
print(os.path.abspath(sys.argv[1]))
PY
}

RESPONSE_TABLE=""
SHARED_FEATURES_DIR=""
OUTPUT_DIR=""
MODEL_CONFIG="${AIXPORT_REPO}/configs/custom_dataset_models.json"
DRUG_COL="drug"
CELL_COL="cell_line"
GROUP_COL=""
LABEL_COL="auc"
SMILES_COL="smiles"
DATASET_COL="dataset"
DATASET_DEFAULT="custom"
TEST_FRACTION="0.2"
SEED="42"
MIN_ROWS_PER_DRUG="20"
MIN_GROUPS_PER_DRUG="10"
DRUGS=""
LABEL_TRANSFORM="none"
LOG2_OFFSET="1.0"
RUN_HPO="auto"
SKIP_BENCHMARK=0
SKIP_INSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --response-table)
      RESPONSE_TABLE="$(abs_path "$2")"
      shift 2
      ;;
    --shared-features-dir)
      SHARED_FEATURES_DIR="$(abs_path "$2")"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$(abs_path "$2")"
      shift 2
      ;;
    --model-config)
      MODEL_CONFIG="$(abs_path "$2")"
      shift 2
      ;;
    --drug-col)
      DRUG_COL="$2"
      shift 2
      ;;
    --cell-col)
      CELL_COL="$2"
      shift 2
      ;;
    --group-col)
      GROUP_COL="$2"
      shift 2
      ;;
    --label-col)
      LABEL_COL="$2"
      shift 2
      ;;
    --smiles-col)
      SMILES_COL="$2"
      shift 2
      ;;
    --dataset-col)
      DATASET_COL="$2"
      shift 2
      ;;
    --dataset-default)
      DATASET_DEFAULT="$2"
      shift 2
      ;;
    --test-fraction)
      TEST_FRACTION="$2"
      shift 2
      ;;
    --seed)
      SEED="$2"
      shift 2
      ;;
    --min-rows-per-drug)
      MIN_ROWS_PER_DRUG="$2"
      shift 2
      ;;
    --min-groups-per-drug)
      MIN_GROUPS_PER_DRUG="$2"
      shift 2
      ;;
    --drugs)
      DRUGS="$2"
      shift 2
      ;;
    --label-transform)
      LABEL_TRANSFORM="$2"
      shift 2
      ;;
    --log2-offset)
      LOG2_OFFSET="$2"
      shift 2
      ;;
    --run-hpo)
      RUN_HPO="$2"
      shift 2
      ;;
    --skip-benchmark)
      SKIP_BENCHMARK=1
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${RESPONSE_TABLE}" || -z "${SHARED_FEATURES_DIR}" || -z "${OUTPUT_DIR}" ]]; then
  echo "ERROR: --response-table, --shared-features-dir, and --output-dir are required" >&2
  usage >&2
  exit 1
fi

for path in "${RESPONSE_TABLE}" "${SHARED_FEATURES_DIR}" "${MODEL_CONFIG}"; do
  if [[ ! -e "${path}" ]]; then
    echo "ERROR: Path does not exist: ${path}" >&2
    exit 1
  fi
done

mkdir -p "${OUTPUT_DIR}"

CONFIG_DIR="${OUTPUT_DIR}/pipeline_configs"
ROCRATES_DIR="${OUTPUT_DIR}/rocrates"
OPTIMIZE_OUT="${OUTPUT_DIR}/optimize"
TRAIN_OUT="${OUTPUT_DIR}/trainout"
PREDICT_OUT="${OUTPUT_DIR}/predictout"
BENCHMARK_OUT="${OUTPUT_DIR}/benchmark"
TRAIN_LIST="${OUTPUT_DIR}/train_rocrates.txt"
TEST_LIST="${OUTPUT_DIR}/test_rocrates.txt"

rm -rf "${CONFIG_DIR}" "${ROCRATES_DIR}" "${OPTIMIZE_OUT}" "${TRAIN_OUT}" "${PREDICT_OUT}" "${BENCHMARK_OUT}"
mkdir -p "${CONFIG_DIR}"

SELECTED_CONFIG="${CONFIG_DIR}/selected_algorithms.json"
OPTIMIZE_CONFIG="${CONFIG_DIR}/optimize_algorithms.json"
PASSTHROUGH_CONFIG="${CONFIG_DIR}/passthrough_algorithms.json"
INSTALL_MANIFEST="${CONFIG_DIR}/install_manifest.tsv"
FINAL_CONFIG="${CONFIG_DIR}/final_algorithms.json"

echo "=== Resolving enabled models from JSON ==="
"${PYTHON_BIN}" - "${MODEL_CONFIG}" "${RUN_HPO}" "${ELASTICNET_REPO}" "${RANDOMFOREST_REPO}" "${XGBOOST_REPO}" "${NEST_VNN_REPO}" "${SELECTED_CONFIG}" "${OPTIMIZE_CONFIG}" "${PASSTHROUGH_CONFIG}" "${INSTALL_MANIFEST}" <<'PY'
import json
import os
import sys

config_path, run_hpo = sys.argv[1], sys.argv[2]
elasticnet_repo, randomforest_repo, xgboost_repo, nest_repo = sys.argv[3:7]
selected_out, optimize_out, passthrough_out, install_out = sys.argv[7:11]

DEFAULT_INSTALLS = {
    "elasticnet_drecmd.py": elasticnet_repo,
    "randomforest_drecmd.py": randomforest_repo,
    "xgboost_drecmd.py": xgboost_repo,
    "nest_vnn_drecmd.py": nest_repo,
}
DEFAULT_OPTIMIZE_TRUE = {
    "elasticnet_drecmd.py",
    "randomforest_drecmd.py",
    "xgboost_drecmd.py",
}

with open(config_path) as f:
    raw = json.load(f)
if not isinstance(raw, dict):
    raise SystemExit("Model config JSON must be a top-level object")

config_dir = os.path.dirname(os.path.abspath(config_path))

def resolve_install_path(command, settings):
    install_path = settings.get("install_path", "") if isinstance(settings, dict) else ""
    if install_path:
        if not os.path.isabs(install_path):
            install_path = os.path.abspath(os.path.join(config_dir, install_path))
        return install_path
    default_path = DEFAULT_INSTALLS.get(os.path.basename(command), "")
    if default_path and os.path.exists(default_path):
        return os.path.abspath(default_path)
    return ""

def should_optimize(command, settings):
    mode = str(run_hpo).strip().lower()
    if mode in {"false", "0", "no", "off"}:
        return False
    if mode in {"true", "1", "yes", "on"}:
        return True
    if isinstance(settings, dict) and "optimize" in settings:
        return bool(settings.get("optimize"))
    return os.path.basename(command) in DEFAULT_OPTIMIZE_TRUE

selected = {}
optimize = {}
passthrough = {}
install_rows = []
seen_commands = set()

for key, settings in raw.items():
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        raise SystemExit(f"Configuration for {key!r} must be an object or null")

    if not settings.get("enabled", True):
        continue

    command = settings.get("command", key)
    if not command:
        raise SystemExit(f"Model entry {key!r} resolved to an empty command")
    if command in seen_commands:
        raise SystemExit(f"Duplicate command after normalization: {command}")
    seen_commands.add(command)

    config_value = settings.get("config", "")
    if config_value is None:
        config_value = ""
    config_by_rocrate = settings.get("config_by_rocrate", {})
    if config_by_rocrate is None:
        config_by_rocrate = {}
    if not isinstance(config_by_rocrate, dict):
        raise SystemExit(f"config_by_rocrate for {key!r} must be an object")

    aixport_entry = {
        "config": config_value,
        "config_by_rocrate": config_by_rocrate,
    }
    selected[command] = aixport_entry
    if should_optimize(command, settings):
        optimize[command] = aixport_entry
    else:
        passthrough[command] = aixport_entry

    install_rows.append((command, resolve_install_path(command, settings)))

if not selected:
    raise SystemExit("No enabled models were found in the model config JSON")

for path, payload in (
    (selected_out, selected),
    (optimize_out, optimize),
    (passthrough_out, passthrough),
):
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")

with open(install_out, "w") as f:
    f.write("command\tinstall_path\n")
    for command, install_path in install_rows:
        f.write(f"{command}\t{install_path}\n")

print(f"Enabled models : {len(selected)}")
print(f"Optimize models: {len(optimize)}")
print(f"Pass-through   : {len(passthrough)}")
PY

if [[ "${SKIP_INSTALL}" != "1" ]]; then
  echo "=== Installing aixport and enabled model packages ==="
  "${PYTHON_BIN}" -m pip install --no-deps -e "${AIXPORT_REPO}"
  while IFS=$'\t' read -r command install_path; do
    if [[ "${command}" == "command" ]]; then
      continue
    fi
    if [[ -n "${install_path}" ]]; then
      echo "Installing ${command} from ${install_path}"
      "${PYTHON_BIN}" -m pip install --no-deps -e "${install_path}"
    fi
  done < "${INSTALL_MANIFEST}"
fi

echo "=== Verifying aixport and model commands ==="
if ! command -v aixportcmd.py >/dev/null 2>&1; then
  echo "ERROR: aixportcmd.py is not on PATH after installation" >&2
  exit 1
fi
while IFS=$'\t' read -r command install_path; do
  if [[ "${command}" == "command" ]]; then
    continue
  fi
  if [[ -x "${command}" ]]; then
    continue
  fi
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "ERROR: Model command not found on PATH: ${command}" >&2
    if [[ -n "${install_path}" ]]; then
      echo "Tried install_path: ${install_path}" >&2
    fi
    exit 1
  fi
done < "${INSTALL_MANIFEST}"

echo "=== Building custom RO-Crates ==="
"${PYTHON_BIN}" "${SCRIPT_DIR}/create_custom_rocrates.py" \
  --response_table "${RESPONSE_TABLE}" \
  --shared_features_dir "${SHARED_FEATURES_DIR}" \
  --output_dir "${ROCRATES_DIR}" \
  --drug_col "${DRUG_COL}" \
  --cell_col "${CELL_COL}" \
  --group_col "${GROUP_COL}" \
  --label_col "${LABEL_COL}" \
  --smiles_col "${SMILES_COL}" \
  --dataset_col "${DATASET_COL}" \
  --dataset_default "${DATASET_DEFAULT}" \
  --test_fraction "${TEST_FRACTION}" \
  --seed "${SEED}" \
  --min_rows_per_drug "${MIN_ROWS_PER_DRUG}" \
  --min_groups_per_drug "${MIN_GROUPS_PER_DRUG}" \
  --drugs "${DRUGS}" \
  --label_transform "${LABEL_TRANSFORM}" \
  --log2_offset "${LOG2_OFFSET}"

find "${ROCRATES_DIR}" -type d -name "*_train_rocrate" | sort > "${TRAIN_LIST}"
find "${ROCRATES_DIR}" -type d -name "*_test_rocrate" | sort > "${TEST_LIST}"

if [[ ! -s "${TRAIN_LIST}" || ! -s "${TEST_LIST}" ]]; then
  echo "ERROR: No train/test RO-Crates were created under ${ROCRATES_DIR}" >&2
  exit 1
fi

echo "Train rocrates: $(wc -l < "${TRAIN_LIST}")"
echo "Test  rocrates: $(wc -l < "${TEST_LIST}")"

if [[ -s "${OPTIMIZE_CONFIG}" ]] && [[ "$("${PYTHON_BIN}" - "${OPTIMIZE_CONFIG}" <<'PY'
import json
import sys
with open(sys.argv[1]) as f:
    data = json.load(f)
print("1" if data else "0")
PY
)" == "1" ]]; then
  echo "=== Running hyperparameter optimization ==="
  aixportcmd.py optimize-train "${OPTIMIZE_OUT}" \
    --input "${TRAIN_LIST}" \
    --algorithms "${OPTIMIZE_CONFIG}" \
    --cv_folds 3 \
    --preset fast \
    --max_combos 24

  OPTIMIZED_CONFIG="${OPTIMIZE_OUT}/optimized_algorithms.json"
  if [[ ! -f "${OPTIMIZED_CONFIG}" ]]; then
    echo "ERROR: Missing optimized config at ${OPTIMIZED_CONFIG}" >&2
    exit 1
  fi

  echo "=== Merging optimized and pass-through configs ==="
  "${PYTHON_BIN}" - "${SELECTED_CONFIG}" "${OPTIMIZED_CONFIG}" "${FINAL_CONFIG}" <<'PY'
import json
import sys

selected_path, optimized_path, final_path = sys.argv[1:4]
with open(selected_path) as f:
    selected = json.load(f)
with open(optimized_path) as f:
    optimized = json.load(f)

final = {}
for command, payload in selected.items():
    final[command] = optimized.get(command, payload)

with open(final_path, "w") as f:
    json.dump(final, f, indent=2, sort_keys=True)
    f.write("\n")
PY
else
  cp "${SELECTED_CONFIG}" "${FINAL_CONFIG}"
fi

echo "=== Validating required feature tables ==="
"${PYTHON_BIN}" - "${FINAL_CONFIG}" "${TRAIN_LIST}" "${TEST_LIST}" <<'PY'
import json
import os
import re
import sys

config_path, train_list, test_list = sys.argv[1:4]
FEATURE_PRESETS = {
    "all": ["mutations", "cnd", "cna"],
    "all4": ["mutations", "cnd", "cna", "expression"],
    "mutations": ["mutations"],
    "mutation": ["mutations"],
    "mut": ["mutations"],
    "cna": ["cna"],
    "amplification": ["cna"],
    "amplifications": ["cna"],
    "amp": ["cna"],
    "cnd": ["cnd"],
    "deletion": ["cnd"],
    "deletions": ["cnd"],
    "del": ["cnd"],
    "fusion": ["fusion"],
    "fusions": ["fusion"],
    "expression": ["expression"],
    "expr": ["expression"],
}
FEATURE_FILES = {
    "mutations": "cell2mutation.txt",
    "cnd": "cell2cndeletion.txt",
    "cna": "cell2cnamplification.txt",
    "fusion": "cell2fusion.txt",
    "expression": "cell2expression.txt",
}

def extend_tokens(value, resolved):
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            extend_tokens(item, resolved)
        return
    text = str(value).strip()
    if not text:
        return
    lower = text.lower()
    if lower in FEATURE_PRESETS:
        for token in FEATURE_PRESETS[lower]:
            if token not in resolved:
                resolved.append(token)
        return
    for part in [p for p in re.split(r"[\s,;+|]+", lower) if p]:
        if part not in FEATURE_PRESETS:
            continue
        for token in FEATURE_PRESETS[part]:
            if token not in resolved:
                resolved.append(token)

def resolve_feature_types(section_cfg):
    if not isinstance(section_cfg, dict):
        return []
    if section_cfg.get("feature_types") in (None, "") and section_cfg.get("genomic_features") in (None, ""):
        return []
    resolved = []
    source = section_cfg.get("feature_types")
    if source in (None, ""):
        source = section_cfg.get("genomic_features")
    extend_tokens(source, resolved)
    return resolved

with open(config_path) as f:
    data = json.load(f)

required_files = set()
for settings in data.values():
    config = settings.get("config", {})
    if isinstance(config, dict):
        for section_name in ("train", "test"):
            for feature_type in resolve_feature_types(config.get(section_name, {})):
                required_files.add(FEATURE_FILES[feature_type])
    for rocrate_cfg in (settings.get("config_by_rocrate", {}) or {}).values():
        if isinstance(rocrate_cfg, dict):
            for section_name in ("train", "test"):
                for feature_type in resolve_feature_types(rocrate_cfg.get(section_name, {})):
                    required_files.add(FEATURE_FILES[feature_type])

missing = []
for list_path in (train_list, test_list):
    with open(list_path) as f:
        for line in f:
            crate = line.strip()
            if not crate:
                continue
            for filename in sorted(required_files):
                if not os.path.exists(os.path.join(crate, filename)):
                    missing.append((crate, filename))

if missing:
    examples = "\n".join(f"  {crate} -> {filename}" for crate, filename in missing[:10])
    raise SystemExit("Missing required feature files for selected model config:\n" + examples)

print("Required feature files: " + (", ".join(sorted(required_files)) if required_files else "none"))
PY

echo "=== Training enabled models ==="
aixportcmd.py train "${TRAIN_OUT}" \
  --input "${TRAIN_LIST}" \
  --algorithms "${FINAL_CONFIG}" \
  --run_mode bash
bash "${TRAIN_OUT}/bash_train_job.sh"

if [[ ! -d "${TRAIN_OUT}/trainedmodels" ]]; then
  echo "ERROR: Missing trainedmodels directory at ${TRAIN_OUT}/trainedmodels" >&2
  exit 1
fi

echo "=== Predicting on test RO-Crates ==="
aixportcmd.py predict "${PREDICT_OUT}" \
  --input "${TEST_LIST}" \
  --trainedmodels "${TRAIN_OUT}/trainedmodels" \
  --algorithms "${FINAL_CONFIG}" \
  --run_mode bash
bash "${PREDICT_OUT}/bash_predict_job.sh"

if [[ "${SKIP_BENCHMARK}" != "1" ]]; then
  echo "=== Benchmarking predictions ==="
  aixportcmd.py benchmark "${BENCHMARK_OUT}" \
    --input_test_rocrates "${TEST_LIST}" \
    --predictions_rocrate "${PREDICT_OUT}"
fi

echo ""
echo "Done."
echo "RO-Crates:   ${ROCRATES_DIR}"
echo "Train:       ${TRAIN_OUT}"
echo "Predict:     ${PREDICT_OUT}"
if [[ "${SKIP_BENCHMARK}" != "1" ]]; then
  echo "Benchmark:   ${BENCHMARK_OUT}"
fi
echo "Config used: ${FINAL_CONFIG}"
