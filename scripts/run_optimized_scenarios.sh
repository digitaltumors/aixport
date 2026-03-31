#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_optimized_scenarios.sh \
    --outdir /path/to/output \
    --ccle-v2-dir /path/to/ccle_v2 \
    --ccle-to-msk-dir /path/to/ccle_to_msk_393 \
    --msk-dir /path/to/msk_chord \
    [--msk-to-ccle-dir /path/to/msk_to_ccle_393] \
    [--scenarios all|comma,list] \
    [--cv-folds 3] \
    [--preset fast|standard] \
    [--max-combos 24] \
    [--skip-install]

This script reproduces the 3-model optimize-train -> train -> predict -> benchmark
workflow using:
  - elasticnet_drecmd.py
  - randomforest_drecmd.py
  - xgboost_drecmd.py

Scenarios:
  scenario1_ccle_v2
  scenario2_ccle_to_msk
  scenario3_pure_msk
  scenario4_msk_to_ccle
  scenario5_ccle_v2_all4

Notes:
  - By default, the script expects the four repos to live side-by-side:
      <workspace>/aixport
      <workspace>/elasticnet_dre
      <workspace>/randomforest_dre
      <workspace>/xgboost_dre
  - Override repo locations with:
      ELASTICNET_REPO
      RANDOMFOREST_REPO
      XGBOOST_REPO
      AIXPORT_REPO
  - Override Python with PYTHON_BIN=/path/to/python
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIXPORT_REPO="${AIXPORT_REPO:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "${AIXPORT_REPO}/.." && pwd)}"
ELASTICNET_REPO="${ELASTICNET_REPO:-${WORKSPACE_ROOT}/elasticnet_dre}"
RANDOMFOREST_REPO="${RANDOMFOREST_REPO:-${WORKSPACE_ROOT}/randomforest_dre}"
XGBOOST_REPO="${XGBOOST_REPO:-${WORKSPACE_ROOT}/xgboost_dre}"
PYTHON_BIN="${PYTHON_BIN:-python}"

OUTDIR="${OUTDIR:-}"
SCENARIOS="${SCENARIOS:-all}"
CV_FOLDS="${CV_FOLDS:-3}"
OPT_PRESET="${OPT_PRESET:-fast}"
MAX_COMBOS="${MAX_COMBOS:-24}"
SKIP_INSTALL=0

CCLE_V2_DIR="${CCLE_V2_DIR:-}"
CCLE_TO_MSK_DIR="${CCLE_TO_MSK_DIR:-}"
MSK_DIR="${MSK_DIR:-}"
MSK_TO_CCLE_DIR="${MSK_TO_CCLE_DIR:-}"
BASE_ALGO_CONFIG="${BASE_ALGO_CONFIG:-${AIXPORT_REPO}/configs/aixport_models.json}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --outdir)
      OUTDIR="$(realpath "$2")"
      shift 2
      ;;
    --ccle-v2-dir)
      CCLE_V2_DIR="$(realpath "$2")"
      shift 2
      ;;
    --ccle-to-msk-dir)
      CCLE_TO_MSK_DIR="$(realpath "$2")"
      shift 2
      ;;
    --msk-dir)
      MSK_DIR="$(realpath "$2")"
      shift 2
      ;;
    --msk-to-ccle-dir)
      MSK_TO_CCLE_DIR="$(realpath "$2")"
      shift 2
      ;;
    --scenarios)
      SCENARIOS="$2"
      shift 2
      ;;
    --cv-folds)
      CV_FOLDS="$2"
      shift 2
      ;;
    --preset)
      OPT_PRESET="$2"
      shift 2
      ;;
    --max-combos)
      MAX_COMBOS="$2"
      shift 2
      ;;
    --base-algo-config)
      BASE_ALGO_CONFIG="$(realpath "$2")"
      shift 2
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

if [[ -z "${OUTDIR}" ]]; then
  echo "ERROR: --outdir is required" >&2
  usage >&2
  exit 1
fi

if [[ ! -f "${BASE_ALGO_CONFIG}" ]]; then
  echo "ERROR: Missing base algorithm config: ${BASE_ALGO_CONFIG}" >&2
  exit 1
fi

DEFAULT_ALL_SCENARIOS="scenario1_ccle_v2,scenario2_ccle_to_msk,scenario3_pure_msk,scenario4_msk_to_ccle,scenario5_ccle_v2_all4"

selected_scenarios() {
  if [[ "${SCENARIOS}" == "all" ]]; then
    echo "${DEFAULT_ALL_SCENARIOS}"
  else
    echo "${SCENARIOS}"
  fi
}

should_run_scenario() {
  local name="$1"
  local selected token
  selected="$(selected_scenarios)"
  IFS=',' read -r -a _scenario_tokens <<< "${selected}"
  for token in "${_scenario_tokens[@]}"; do
    if [[ "${token}" == "${name}" ]]; then
      return 0
    fi
  done
  return 1
}

require_dir_for_scenario() {
  local scenario_name="$1"
  local rocrate_dir="$2"
  if [[ -z "${rocrate_dir}" ]]; then
    echo "ERROR: ${scenario_name} selected but its RO-Crate directory was not provided." >&2
    exit 1
  fi
  if [[ ! -d "${rocrate_dir}" ]]; then
    echo "ERROR: RO-Crate directory does not exist for ${scenario_name}: ${rocrate_dir}" >&2
    exit 1
  fi
}

if should_run_scenario "scenario1_ccle_v2" || should_run_scenario "scenario5_ccle_v2_all4"; then
  require_dir_for_scenario "scenario1_ccle_v2/scenario5_ccle_v2_all4" "${CCLE_V2_DIR}"
fi
if should_run_scenario "scenario2_ccle_to_msk"; then
  require_dir_for_scenario "scenario2_ccle_to_msk" "${CCLE_TO_MSK_DIR}"
fi
if should_run_scenario "scenario3_pure_msk"; then
  require_dir_for_scenario "scenario3_pure_msk" "${MSK_DIR}"
fi
if should_run_scenario "scenario4_msk_to_ccle"; then
  require_dir_for_scenario "scenario4_msk_to_ccle" "${MSK_TO_CCLE_DIR}"
fi

cleanup_selected_scenarios() {
  local scenario_name
  for scenario_name in \
    scenario1_ccle_v2 \
    scenario2_ccle_to_msk \
    scenario3_pure_msk \
    scenario4_msk_to_ccle \
    scenario5_ccle_v2_all4; do
    if should_run_scenario "${scenario_name}"; then
      rm -rf "${OUTDIR}/${scenario_name}"
    fi
  done
}

config_requires_expression() {
  local algo_config="$1"
  "${PYTHON_BIN}" - <<PY
import json

with open("${algo_config}") as f:
    cfg = json.load(f)

requires_expression = False
for algo_cfg in cfg.values():
    inner = algo_cfg.get("config", {})
    for section in ("train", "test"):
        section_cfg = inner.get(section, {})
        genomic_features = section_cfg.get("genomic_features", "all")
        feature_types = section_cfg.get("feature_types", [])
        if genomic_features in ("all4", "expression"):
            requires_expression = True
        if isinstance(feature_types, str):
            feature_types = [token.strip() for token in feature_types.split(",") if token.strip()]
        if "expression" in feature_types:
            requires_expression = True
print("1" if requires_expression else "0")
PY
}

validate_expression_inputs() {
  local train_list="$1"
  local test_list="$2"
  local missing_train
  local missing_test

  missing_train="$("${PYTHON_BIN}" - <<PY
from pathlib import Path
missing = []
with open("${train_list}") as f:
    for line in f:
        crate = Path(line.strip())
        if crate and crate.exists() and not (crate / "cell2expression.txt").exists():
            missing.append(str(crate))
print("\\n".join(missing[:5]))
print("COUNT=" + str(len(missing)))
PY
)"
  missing_test="$("${PYTHON_BIN}" - <<PY
from pathlib import Path
missing = []
with open("${test_list}") as f:
    for line in f:
        crate = Path(line.strip())
        if crate and crate.exists() and not (crate / "cell2expression.txt").exists():
            missing.append(str(crate))
print("\\n".join(missing[:5]))
print("COUNT=" + str(len(missing)))
PY
)"

  local train_count="${missing_train##*COUNT=}"
  local test_count="${missing_test##*COUNT=}"
  if [[ "${train_count}" != "0" || "${test_count}" != "0" ]]; then
    echo "ERROR: The selected config requires expression, but some RO-Crates are missing cell2expression.txt." >&2
    echo "Missing train expression files: ${train_count}" >&2
    echo "Missing test expression files : ${test_count}" >&2
    echo "Example missing train RO-Crates:" >&2
    echo "${missing_train%COUNT=*}" >&2
    return 1
  fi
}

if [[ "${SKIP_INSTALL}" != "1" ]]; then
  echo "=== Reinstalling local packages ==="
  "${PYTHON_BIN}" -m pip install --no-deps -e "${ELASTICNET_REPO}"
  "${PYTHON_BIN}" -m pip install --no-deps -e "${RANDOMFOREST_REPO}"
  "${PYTHON_BIN}" -m pip install --no-deps -e "${XGBOOST_REPO}"
  "${PYTHON_BIN}" -m pip install --no-deps -e "${AIXPORT_REPO}"
fi

mkdir -p "${OUTDIR}"
cleanup_selected_scenarios

THREE_MODEL_ALGO_CONFIG="${OUTDIR}/aixport_models_3_only.json"
THREE_MODEL_ALL4_ALGO_CONFIG="${OUTDIR}/aixport_models_3_only_all4.json"
rm -f "${THREE_MODEL_ALGO_CONFIG}" "${THREE_MODEL_ALL4_ALGO_CONFIG}"

echo "=== Building 3-model algorithm configs ==="
"${PYTHON_BIN}" - <<PY
import json

base = "${BASE_ALGO_CONFIG}"
out = "${THREE_MODEL_ALGO_CONFIG}"
out_all4 = "${THREE_MODEL_ALL4_ALGO_CONFIG}"
keep = {
    "elasticnet_drecmd.py",
    "randomforest_drecmd.py",
    "xgboost_drecmd.py",
}

with open(base) as f:
    cfg = json.load(f)

cfg = {k: v for k, v in cfg.items() if k in keep}
missing = sorted(list(keep - set(cfg.keys())))
if missing:
    raise SystemExit("Missing expected algorithms in base config: " + ", ".join(missing))

with open(out, "w") as f:
    json.dump(cfg, f, indent=2, sort_keys=True)

cfg_all4 = json.loads(json.dumps(cfg))
for algo_cfg in cfg_all4.values():
    inner = algo_cfg.get("config", {})
    for section in ("train", "test"):
        section_cfg = inner.setdefault(section, {})
        section_cfg["feature_types"] = ["mutations", "cnd", "cna", "expression"]
        section_cfg["genomic_features"] = "all4"

with open(out_all4, "w") as f:
    json.dump(cfg_all4, f, indent=2, sort_keys=True)

print("Wrote", out)
print("Wrote", out_all4)
PY

run_scenario() {
  local scenario_name="$1"
  local rocrates_dir="$2"
  local algo_config="${3:-${THREE_MODEL_ALGO_CONFIG}}"

  local outdir="${OUTDIR}/${scenario_name}"
  local train_list="${outdir}/train_rocrates.txt"
  local test_list="${outdir}/test_rocrates.txt"
  local optimize_out="${outdir}/optimize"
  local train_out="${outdir}/trainout"
  local predict_out="${outdir}/predictout"
  local benchmark_out="${outdir}/benchmark"

  echo ""
  echo "============================================================"
  echo "Scenario : ${scenario_name}"
  echo "RO-Crates: ${rocrates_dir}"
  echo "Config   : ${algo_config}"
  echo "Output   : ${outdir}"
  echo "============================================================"

  rm -rf "${outdir}"
  mkdir -p "${outdir}"

  find "${rocrates_dir}" -type d -name "*_train_rocrate" | sort > "${train_list}"
  find "${rocrates_dir}" -type d -name "*_test_rocrate" | sort > "${test_list}"

  if [[ ! -s "${train_list}" || ! -s "${test_list}" ]]; then
    echo "ERROR: No train/test RO-Crates found under ${rocrates_dir}" >&2
    return 1
  fi

  echo "Train rocrates: $(wc -l < "${train_list}")"
  echo "Test  rocrates: $(wc -l < "${test_list}")"

  if [[ "$(config_requires_expression "${algo_config}")" == "1" ]]; then
    validate_expression_inputs "${train_list}" "${test_list}"
  fi

  echo "--- optimize-train (${scenario_name}) ---"
  aixportcmd.py optimize-train "${optimize_out}" \
    --input "${train_list}" \
    --algorithms "${algo_config}" \
    --cv_folds "${CV_FOLDS}" \
    --preset "${OPT_PRESET}" \
    --max_combos "${MAX_COMBOS}"

  local optimized_algos="${optimize_out}/optimized_algorithms.json"
  if [[ ! -f "${optimized_algos}" ]]; then
    echo "ERROR: Missing optimized config at ${optimized_algos}" >&2
    return 1
  fi

  echo "--- train (${scenario_name}) ---"
  aixportcmd.py train "${train_out}" \
    --input "${train_list}" \
    --algorithms "${optimized_algos}" \
    --run_mode bash
  bash "${train_out}/bash_train_job.sh"

  local trainedmodels="${train_out}/trainedmodels"
  if [[ ! -d "${trainedmodels}" ]]; then
    echo "ERROR: Missing trainedmodels directory at ${trainedmodels}" >&2
    return 1
  fi

  echo "--- predict (${scenario_name}) ---"
  aixportcmd.py predict "${predict_out}" \
    --input "${test_list}" \
    --trainedmodels "${trainedmodels}" \
    --algorithms "${optimized_algos}" \
    --run_mode bash
  bash "${predict_out}/bash_predict_job.sh"

  echo "--- benchmark (${scenario_name}) ---"
  aixportcmd.py benchmark "${benchmark_out}" \
    --input_test_rocrates "${test_list}" \
    --predictions_rocrate "${predict_out}"
}

if should_run_scenario "scenario1_ccle_v2"; then
  run_scenario "scenario1_ccle_v2" "${CCLE_V2_DIR}"
fi

if should_run_scenario "scenario2_ccle_to_msk"; then
  run_scenario "scenario2_ccle_to_msk" "${CCLE_TO_MSK_DIR}"
fi

if should_run_scenario "scenario3_pure_msk"; then
  run_scenario "scenario3_pure_msk" "${MSK_DIR}"
fi

if should_run_scenario "scenario4_msk_to_ccle"; then
  run_scenario "scenario4_msk_to_ccle" "${MSK_TO_CCLE_DIR}"
fi

if should_run_scenario "scenario5_ccle_v2_all4"; then
  run_scenario "scenario5_ccle_v2_all4" "${CCLE_V2_DIR}" "${THREE_MODEL_ALL4_ALGO_CONFIG}"
fi

echo ""
echo "All selected optimized scenario runs completed."
echo "Results are under: ${OUTDIR}"
