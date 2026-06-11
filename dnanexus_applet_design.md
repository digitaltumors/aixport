# Design: Multiple DNAnexus Applets for AIxPORT

## Purpose

Create a repo-local `.dnanexus/` packaging layer for `aixport` and wire it into
`dx-drpmodel-applet-generator` so AIxPORT workflows can run on DNAnexus as
separate applets.

The recommended design is one shared AIxPORT Docker image with multiple
DNAnexus applet wrappers. Each applet maps to one clear AIxPORT workflow and
has its own `dxapp.json` input and output contract. This avoids a single
overloaded applet with many optional inputs that are only valid for some
commands.

## Recommended Applets

Start with these applets:

```text
aixport_vcf2inputs       Converts annotated VCF files into AIxPORT or MutationProjector inputs.
aixport_benchmark        Runs benchmark scoring on prediction RO-Crates.
```

`aixport_vcf2inputs` should be implemented first because it is self-contained:
uploaded files go in, a complete output RO-Crate comes out. `aixport_benchmark`
is also a direct execution applet after dependency and exit-code fixes.

## Repositories Reviewed

### `aixport/`

- `aixport/aixportcmd.py` is the installed CLI entry point. It registers
  `train`, `predict`, `benchmark`, `evaluate`, pipeline commands, and
  `vcf2inputs`.
- `setup.py` installs `aixport/aixportcmd.py` as a script and includes bundled
  gene-panel package data.
- `docker/Dockerfile` already builds a simple container with
  `ENTRYPOINT ["/opt/conda/bin/aixportcmd.py"]`.
- `vcf2inputs` directly creates an output directory with RO-Crate metadata,
  matrix files, and conversion audit files.
- `train` and `predict` currently generate scripts and manifests.
- `benchmark` directly computes results, but imports `pandas` and `numpy`,
  which are not declared in `setup.py`; it also currently returns `99` after a
  successful run.

### `MutationProjector/`

MutationProjector provides the repo-local packaging pattern to mirror:

```text
.dnanexus/
  Makefile
  conf.yml
  docker/Dockerfile
  help.md
  run.sh
```

Its Dockerfile builds from the repository root, copies `.dnanexus/run.sh`, and
uses that script as the container entrypoint. Its `.dnanexus/conf.yml` provides
metadata and the version consumed by the applet generator.

### `dx-drpmodel-applet-generator/`

The generator builds applets from `applets.yaml` plus template directories:

- `Makefile` exposes `make applet/<id>`, `make docker/<id>`,
  `make deploy/<id>`, and smoke-test targets.
- `scripts/applets.py` resolves `version_file`, Docker image settings,
  template paths, and placeholder values.
- `container.tar` can copy a prebuilt image tarball instead of rebuilding a
  Docker image. Use that to let multiple AIxPORT applets reuse the same image.
- `dre_model_template` wraps individual model images, not AIxPORT workflows, so
  AIxPORT should get dedicated templates.

Implementation note: every new template script should end with `main "$@"`.
Some existing templates define `main` but do not invoke it; do not copy that
mistake into the new AIxPORT templates.

## Shared AIxPORT Docker Layer

Add this tree to `aixport/`:

```text
.dnanexus/
  Makefile
  conf.yml
  docker/
    Dockerfile
  help.md
  run.sh
```

### `.dnanexus/conf.yml`

Use the same metadata shape as the existing DRE and MutationProjector projects:

```yaml
author: "Dynamic Digital Tumors for Precision Oncology Team"
email: "hello@digitaltumors.org"
version: "0.1.0"
repo_url: "https://github.com/digitaltumors/aixport"
description: "AIxPORT command-line tools for oncology model input conversion, training workflow generation, prediction workflow generation, and benchmarking."
computation_name: "AIxPORT"
applet_id: "aixport"
image: "digitaltumors/aixport"
dockerfile: ".dnanexus/docker/Dockerfile"
```

Keep `version` synchronized with `aixport/__init__.py`. Also fix
`aixport.__repo_url__`, which currently points at `digitaltumors/dreutils`
instead of `digitaltumors/aixport`.

### `.dnanexus/run.sh`

The container entrypoint should be a thin pass-through to the installed CLI:

```bash
#!/bin/bash
set -euo pipefail

exec /opt/conda/bin/aixportcmd.py "$@"
```

This keeps the image generic. Applet templates decide which subcommand and
arguments to pass.

### `.dnanexus/docker/Dockerfile`

Base the DNAnexus image on the existing `docker/Dockerfile`, but make it
explicitly suitable for applet builds:

```Dockerfile
FROM continuumio/miniconda3

RUN apt-get --allow-releaseinfo-change update && \
    apt-get install -y --no-install-recommends build-essential ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/aixport
COPY ./ /opt/aixport/
RUN python -m pip install --no-cache-dir /opt/aixport && \
    python -m pip check

COPY .dnanexus/run.sh /opt/aixport/run.sh
RUN chmod a+x /opt/aixport/run.sh

ENTRYPOINT ["/opt/aixport/run.sh"]
CMD ["--help"]
```

Before relying on `aixport_benchmark`, update package metadata so `pandas` and
`numpy` are installed. If `python -m pip check` exposes dependency gaps, fix
those in `setup.py` and `requirements.txt` rather than installing packages only
in the Dockerfile.

### `.dnanexus/Makefile`

Mirror MutationProjector's repo-local Docker target:

```make
.PHONY: help docker
.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys
for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

docker: ## Builds AIxPORT Docker image
	@cd .. ;\
	cv=`grep 'version' .dnanexus/conf.yml | sed "s/^.*: *\"//" | sed "s/\".*//"`; \
	docker buildx build --platform linux/amd64 \
		-t digitaltumors/aixport:$$cv \
		-f .dnanexus/docker/Dockerfile .;
```

The generator remains the deploy path. This Makefile is for local image builds
and quick checks from the `aixport` repository.

## Generator Layout

Add one template directory per applet to
`dx-drpmodel-applet-generator/`:

```text
aixport_vcf2inputs_template/
  Readme.developer.md
  Readme.md
  dxapp.json
  src/script.sh
  test/test.py

aixport_benchmark_template/
  Readme.developer.md
  Readme.md
  dxapp.json
  src/script.sh
  test/test.py
```

These templates can share shell helper functions, but keep the rendered
`dxapp.json` files separate. DNAnexus applets have static input specs, so
separate templates are much easier to validate and smoke test.

## `applets.yaml` Strategy

Build the Docker image tarball once, then copy it for the other AIxPORT applets.
The current generator can do this with `container.tar`.

The first AIxPORT applet should build the shared image:

```yaml
- id: aixport_vcf2inputs
  name: aixport_vcf2inputs
  title: AIxPORT VCF to Inputs
  summary: Converts annotated VCF files into AIxPORT or MutationProjector genomic input files.
  version_file: ../aixport/.dnanexus/conf.yml
  version_key: version
  project: project-J5JzB8j0vZ9Xqvgp5FX6pbx1
  destination: /applets/aixport_vcf2inputs
  template_dir: aixport_vcf2inputs_template
  instance_type: mem1_ssd1_v2_x8
  container:
      dockerfile: ../aixport/.dnanexus/docker/Dockerfile
      context: ../aixport
      image: digitaltumors/aixport
      name: aixport
      platform: linux/amd64
  smoke:
      enabled: true
      input: smoke/aixport_vcf2inputs/input.json
      destination: /smoke-tests/aixport_vcf2inputs
      timeout_minutes: 30
      required_outputs:
          - results_tar
          - ro_crate_metadata
          - conversion_report
      validators:
          - nonempty_outputs
```

The remaining applet should copy that tarball:

```yaml
- id: aixport_benchmark
  name: aixport_benchmark
  title: AIxPORT Benchmark
  summary: Benchmarks AIxPORT prediction RO-Crates against matching test RO-Crates.
  version_file: ../aixport/.dnanexus/conf.yml
  version_key: version
  project: project-J5JzB8j0vZ9Xqvgp5FX6pbx1
  destination: /applets/aixport_benchmark
  template_dir: aixport_benchmark_template
  instance_type: mem1_ssd1_v2_x8
  container:
      tar: build/aixport_vcf2inputs/resources/aixport.tar.gz
      image: digitaltumors/aixport
      name: aixport
```

This will still copy the tarball into each applet's `resources/` directory, but
it avoids rebuilding the Docker image for every AIxPORT applet. If duplicate
resource storage becomes a problem, update the generator later with a
first-class shared image/resource target.

## Applet Contracts

### `aixport_vcf2inputs`

This applet runs:

```bash
aixportcmd.py vcf2inputs /out/run ...
```

Inputs:

- `vcf` (`file`, required): annotated `.vcf` or `.vcf.gz`.
- `output_profile` (`string`, default `aixport`): `aixport`, `nest_vnn`, or
  `mutationprojector`.
- `gene_panel` (`string`, default `nest_vnn_718`): bundled gene panel id.
- `gene2ind` (`file`, optional): custom gene panel mapping.
- `sample_map` (`file`, optional): VCF sample to output sample TSV.
- `sample_ids` (`string`, optional): comma-delimited VCF samples to include.
- `annotation_field` (`string`, default `auto`).
- `strict_annotations` (`boolean`, default `false`).
- `include_filtered` (`boolean`, default `false`).
- `min_gq` (`int`, optional).
- `min_dp` (`int`, optional).
- `mutation_effects` (`string`, optional): comma-delimited consequence terms.
- `cn_neutral_low` (`float`, default `1.5`).
- `cn_neutral_high` (`float`, default `2.5`).
- `covariates` (`file`, optional): needed for MutationProjector profile unless
  default covariates are requested.
- `outcomes` (`file`, optional): needed for MutationProjector profile unless
  default outcomes are requested.
- `default_covariates` (`boolean`, default `false`).
- `default_outcomes` (`boolean`, default `false`).

Outputs:

- `results_tar`: tarball of `/out/run`.
- `ro_crate_metadata`: `ro-crate-metadata.json`.
- `conversion_report`: `conversion_report.json`.
- `variants_used`: `variants_used.tsv`.
- `variants_skipped`: `variants_skipped.tsv`.
- `gene2ind`, `cell2ind`, `cell2mutation`, `cell2cnamplification`,
  `cell2cndeletion`: optional outputs for `aixport` and `nest_vnn`.
- `mut`, `cna`, `cnd`, `mutationprojector_covariates`,
  `mutationprojector_outcomes`: optional outputs for `mutationprojector`.
- `task_start`, `task_finish`, `output_log`, `error_log`, `container_log`:
  optional diagnostics.

### `aixport_benchmark`

This applet runs:

```bash
aixportcmd.py benchmark /out/run --input_test_rocrates /work/input_test_rocrates.txt --predictions_rocrate /work/predictions
```

Prerequisites:

- Add `pandas` and `numpy` to runtime dependencies.
- Fix `BenchmarkTool.run()` so a successful benchmark returns `0`, not `99`.

Inputs:

- `test_rocrates` (`array:file`, required): tarballs of test RO-Crate
  directories.
- `predictions_rocrate` (`file`, required): tarball of the prediction RO-Crate
  directory produced by AIxPORT `predict`.

Wrapper behavior:

- Extract test RO-Crates under `/work/test/`.
- Extract the prediction RO-Crate under `/work/predictions`.
- Write `/work/input_test_rocrates.txt`.
- Run `aixportcmd.py benchmark`.

Outputs:

- `results_tar`: tarball of `/out/run`.
- `results_csv`: `results.csv`.
- `results_png`: `results.png`.
- `results_svg`: `results.svg`.
- `ro_crate_metadata`, `task_start`, `task_finish`, `output_log`,
  `error_log`, `container_log`.

## Common Template Behavior

Each `src/script.sh` should:

1. Use `set -euo pipefail`.
2. Create `$HOME/work` and `$HOME/out`.
3. Download required and optional DNAnexus inputs with `dx download`.
4. Load the shared image:

    ```bash
    docker load -i /@@CONTAINER_FILENAME@@
    ```

5. Construct command arguments with Bash arrays. Do not use `eval`.
6. Run the container with read-only work inputs and writable outputs:

    ```bash
    docker run --rm \
      -v "$HOME/work:/work:ro" \
      -v "$HOME/out:/out" \
      "@@CONTAINER_IMAGE@@:@@VERSION@@" \
      "${cmd_args[@]}"
    ```

7. Capture stdout/stderr to a container log while preserving the Docker exit
   code.
8. Upload logs and any files that exist.
9. Upload a tarball of the full `/out/run` directory when it exists.
10. Exit with the original nonzero container status when the command fails.
11. End with `main "$@"`.

Do not append `|| true` to the Docker run. A DNAnexus job should fail when the
AIxPORT command fails.

## Smoke Test Plan

Add one smoke directory per applet:

```text
dx-drpmodel-applet-generator/smoke/
  aixport_vcf2inputs/
    input.json
    fixtures/calls.vcf
    fixtures/gene2ind.txt
  aixport_benchmark/
    input.json
    fixtures/example_test_rocrate.tar.gz
    fixtures/example_predictions_rocrate.tar.gz
```

For `aixport_vcf2inputs`, the smoke input can use local fixture references:

```json
{
    "vcf": { "$local_path": "smoke/aixport_vcf2inputs/fixtures/calls.vcf" },
    "gene2ind": {
        "$local_path": "smoke/aixport_vcf2inputs/fixtures/gene2ind.txt"
    },
    "output_profile": "aixport",
    "gene_panel": "nest_vnn_718",
    "annotation_field": "auto",
    "strict_annotations": false,
    "include_filtered": false,
    "cn_neutral_low": 1.5,
    "cn_neutral_high": 2.5,
    "default_covariates": false,
    "default_outcomes": false
}
```

Validation commands:

```bash
cd dx-drpmodel-applet-generator
make applet/aixport_vcf2inputs
make applet/aixport_benchmark
python scripts/smoke.py run applets.yaml aixport_vcf2inputs --dry-run
make deploy-smoke/aixport_vcf2inputs
```

Enable real smoke tests applet by applet. Do not enable `aixport_benchmark`
smoke until the dependency and exit-code fixes are in place.

## Implementation Order

1. Add the shared `.dnanexus/` files to `aixport/`.
2. Fix package metadata needed by the shared image:
    - update `aixport.__repo_url__`;
    - add `pandas` and `numpy` if `aixport_benchmark` is in scope;
    - make sure `requirements.txt` mirrors runtime dependencies cleanly.
3. Fix `BenchmarkTool.run()` to return `0` on success before deploying
   `aixport_benchmark`.
4. Add `aixport_vcf2inputs_template` and the `aixport_vcf2inputs` entry in
   `applets.yaml`.
5. Add smoke fixtures for `aixport_vcf2inputs`.
6. Build and smoke test `aixport_vcf2inputs`.
7. Add `aixport_benchmark_template` after benchmark dependencies and return
   code are fixed.

## Risks And Decisions

- Multiple applets should share one Docker image. Rebuilding the same image for
  every applet wastes time and increases the chance of version drift.
- `container.tar` reuse avoids repeated Docker builds with the current
  generator, but still stores a copy of the tarball per rendered applet.
- `benchmark` needs dependency and success-exit fixes before deployment.
- DNAnexus applet scripts should not swallow container failures. Upload logs
  first, then exit with the original nonzero status.
- Keep the `.dnanexus/` files in `aixport` repo-local, and keep applet
  rendering/deploy logic in `dx-drpmodel-applet-generator`, matching the
  MutationProjector pattern.
