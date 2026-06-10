# AIxPORT Code Review and VCF Input Conversion Design

## Purpose

This document describes the current AIxPORT code base and proposes a design for
adding a command that converts a Variant Call Format (VCF) file into the genomic
feature files expected by the drug-response model wrappers:

- `gene2ind.txt`
- `cell2ind.txt`
- `cell2mutation.txt`
- `cell2cnamplification.txt`
- `cell2cndeletion.txt`

The first implementation should target the 718-gene feature panel used by
NeST-VNN, while keeping the gene panel and output format configurable so later
models can use additional or different genes. The design also needs to support
MutationProjector, which consumes a different file layout and defaults to the
MSK-IMPACT468 gene set.

External references:

- VCF v4.2 specification: https://samtools.github.io/hts-specs/VCFv4.2.pdf
- NeST-VNN repository: https://github.com/idekerlab/nest_vnn
- MutationProjector repository: https://github.com/idekerlab/MutationProjector

## Current Code Base

AIxPORT is a Python package that provides command line tooling for preparing and
running drug response model workflows. The repository follows a small command
class pattern:

- `aixport/aixportcmd.py` is the script entry point. It creates an `argparse`
  parser, registers each command's subparser, dispatches to the selected command
  class, and maps uncaught exceptions to process exit code `2`.
- `aixport/basecmdtool.py` contains `BaseCommandLineTool`, the shared command
  base class. It creates output directories, initializes RO-Crate metadata,
  configures file logging, writes `task_*_start.json` and
  `task_*_finish.json`, and registers computation provenance through
  `cellmaps_utils`.
- `aixport/train.py` implements `TrainTool` and runners that write bash or
  SLURM scripts for model training. It consumes a file listing training
  RO-Crates and emits scripts plus a `trainedmodels` directory under the output
  RO-Crate.
- `aixport/predict.py` implements `PredictTool` and runners that write bash or
  SLURM scripts for model prediction. It matches `*_test_rocrate` inputs to
  trained model directories named with the `<dataset>_train_rocrate_<algorithm>`
  pattern.
- `aixport/benchmark.py` implements `BenchmarkTool`, which reads prediction
  RO-Crates, compares prediction files against `test_data.txt`, writes
  `results.csv`, and generates `results.png` and `results.svg`.
- `aixport/evaluate.py` and `aixport/pipeline.py` are stubs that currently print
  `Hello world` or are not wired correctly enough for production use.
- `aixport/constants.py` centralizes file names and directory names used across
  the commands, including the five genomic feature file names.
- `aixport/rocratezipper.py` provides a utility for zipping and inspecting
  RO-Crate directory trees.

The package is installed through `setup.py`, which registers
`aixport/aixportcmd.py` as a script. Runtime dependencies are currently sparse:
`cellmaps_utils` and `matplotlib` are listed in `setup.py`, while
`benchmark.py` also imports `pandas` and `numpy`.

## Existing Input Contract

The model input files are documented in `docs/inputs.rst` and represented in
the fixture `tests/data/Palbociclib_test_rocrate/`.

At the root of a training or testing RO-Crate:

- `gene2ind.txt` is a tab-delimited zero-based mapping from gene index to gene
  symbol.
- `cell2ind.txt` is a tab-delimited zero-based mapping from row index to cell
  or genotype identifier.
- `cell2mutation.txt` is a comma-delimited binary matrix. Rows follow
  `cell2ind.txt`; columns follow `gene2ind.txt`; `1` means the gene has a
  non-synonymous mutation in that cell.
- `cell2cndeletion.txt` has the same shape and uses `1` for a copy-number
  deletion event.
- `cell2cnamplification.txt` has the same shape and uses `1` for a copy-number
  amplification event.

The local test fixture uses 718 genes in `gene2ind.txt`, matching the NeST-VNN
README's description of 718 binary genomic features based on mutation and
copy-number status. The NeST-VNN README names its amplification file
`cell2amplification.txt`; AIxPORT's current contract and constants use
`cell2cnamplification.txt`, so the converter should write the AIxPORT name.

MutationProjector has a related but distinct downstream input contract. Its
README documents downstream dataset folders under `data/downstream_data` that
contain tab-delimited files:

- `mut.txt`
- `cna.txt`
- `cnd.txt`
- `covariates.txt`
- `outcomes.txt`

MutationProjector's embedding code reads `mut.txt`, `cna.txt`, and `cnd.txt`
with `pandas.read_csv(..., sep='\t')`, merges them on a `sample` column, sorts
common samples, and stacks the three per-gene matrices as mutation,
copy-number amplification, and copy-number deletion features. Its default
gene set is `MSKIMPACT468`, which resolves to the `MSK-IMPACT468` file and is
sorted after optional gene ID alias conversion.

## Relevant Current Risks

These do not block adding the VCF converter, but the implementation should avoid
copying the same problems:

- `BenchmarkTool.run()` initializes `exitcode = 99` and returns it even after a
  successful benchmark run. It should return `0` on success.
- `EvaluateTool`, `BenchmarkPipelineTool`, and `PredictionPipelineTool` call
  `BaseCommandLineTool.__init__()` without the required `theargs` argument.
- The model interface docs use `--config_file`, while generated train scripts
  use `--config` in one path and a misspelled `--input_rocrate` in the SLURM
  path. New commands should keep argument names internally consistent.
- `SLURMTrainRunner` writes an array range of `1-(len(input_rocrates) + 1)`,
  which appears to create one extra array task.
- The package metadata does not declare all imports used by the benchmark path.
  If a VCF parser dependency is added, it should be declared in `setup.py`,
  `requirements.txt`, and the development requirements.

## Proposed Command

Add a new command named `vcf2inputs`:

```bash
aixportcmd.py vcf2inputs <OUTPUT_DIR> \
    --vcf sample.annotated.vcf.gz \
    --output-profile aixport \
    --gene-panel nest_vnn_718
```

The command creates `<OUTPUT_DIR>` as an AIxPORT RO-Crate. It should parse the
VCF once into a shared internal feature representation, then write files through
a profile-specific output writer. It should also write a conversion report so
users can audit which VCF records were used, skipped, or rejected.

Example with sample renaming and strict annotation validation:

```bash
aixportcmd.py vcf2inputs patient_test_rocrate \
    --vcf patient.annotated.vcf.gz \
    --sample-map sample_map.tsv \
    --output-profile aixport \
    --gene-panel nest_vnn_718 \
    --annotation-field CSQ \
    --strict-annotations
```

Example for MutationProjector:

```bash
aixportcmd.py vcf2inputs mutationprojector_eval_dataset \
    --vcf patient.annotated.vcf.gz \
    --output-profile mutationprojector \
    --gene-panel mutationprojector_mskimpact468 \
    --covariates covariates.txt \
    --outcomes outcomes.txt
```

The `--output-profile` argument should support:

- `aixport`: write the current AIxPORT five-file RO-Crate contract.
- `nest_vnn`: write the NeST-VNN-compatible naming if that diverges from
  AIxPORT in the future.
- `mutationprojector`: write MutationProjector's `mut.txt`, `cna.txt`,
  `cnd.txt`, `covariates.txt`, and `outcomes.txt` layout.

The converter should not infer `test_data.txt`, `training_data.txt`,
`covariates.txt`, or `outcomes.txt` from the VCF. Those files describe
drug-response observations, prediction requests, clinical covariates, or task
labels, not genomic calls. Optional copy/default flags can materialize them in
profile-specific writers, but the core converter should focus on genomic event
extraction.

## VCF Assumptions

The VCF v4.2 specification defines meta-information lines, a `#CHROM` header
line, eight fixed columns, and optional genotype sample columns after `FORMAT`.
The command should support normal `.vcf` and block-gzipped `.vcf.gz` files.

Minimum assumptions for the first implementation:

- The VCF contains genotype sample columns. Each selected VCF sample becomes an
  output sample row, unless `--sample-map` remaps VCF sample IDs to model sample
  IDs.
- Records are assigned to genes through annotations already present in `INFO`.
  VCF itself does not standardize gene symbols or functional consequences, so
  unannotated VCFs cannot safely produce non-synonymous mutation calls.
- Records with `FILTER` equal to `PASS` or `.` are included by default. Other
  filtered records are skipped unless `--include-filtered` is set.
- A sample has a variant call at a record when its genotype is non-reference:
  any called allele value greater than `0` in `GT`, including phased and
  unphased genotypes.
- Missing genotypes such as `./.` or `.` are treated as no call.

Useful optional filters:

- `--min-gq <int>` to require a minimum genotype quality when `GQ` is present.
- `--min-dp <int>` to require a minimum depth when `DP` is present.
- `--include-filtered` to include records that did not pass site filters.
- `--sample <vcf_sample_id>` to restrict output to one VCF sample.

## Gene Panel Design

Do not hard-code the 718 genes in parser logic. Add a small gene panel registry
under package data:

```text
aixport/data/gene_panels/
  nest_vnn_718/
    panel.json
    gene2ind.txt
    aliases.tsv
  mutationprojector_mskimpact468/
    panel.json
    gene2ind.txt
    aliases.tsv
```

`panel.json` should contain metadata such as:

```json
{
  "id": "nest_vnn_718",
  "name": "NeST-VNN 718 gene panel",
  "source": "https://github.com/idekerlab/nest_vnn",
  "gene2ind": "gene2ind.txt",
  "aliases": "aliases.tsv",
  "ordering": "gene2ind"
}
```

A MutationProjector panel should capture the model-specific ordering and alias
policy:

```json
{
  "id": "mutationprojector_mskimpact468",
  "name": "MutationProjector MSK-IMPACT468 gene panel",
  "source": "https://github.com/idekerlab/MutationProjector",
  "gene2ind": "gene2ind.txt",
  "aliases": "aliases.tsv",
  "ordering": "sorted_symbols_after_alias_conversion"
}
```

The command should expose two ways to choose genes:

- `--gene-panel nest_vnn_718`, the default bundled panel.
- `--gene2ind /path/to/gene2ind.txt`, an explicit panel file for expansion or
  testing.

Panel validation rules:

- Indices must be zero-based, contiguous, and unique.
- Gene symbols must be unique after normalization.
- Output matrix width must equal the number of panel genes.
- Only records mapped to genes in the active panel can set matrix values.
- Non-panel genes are skipped and counted in the report.
- Profile writers must use the active panel order exactly. For
  MutationProjector, this means the panel loader must reproduce the sorted
  post-alias gene order used by `load_genes(gset='MSKIMPACT468')`.

Gene symbol matching should be exact and case-sensitive by default. A
case-insensitive fallback and aliases from `aliases.tsv` can be supported, but
the report must record when an alias was used.

## Annotation Extraction

Implement a pluggable annotation extractor so the command can start with common
formats and add more later.

Supported first-pass modes:

- `--annotation-field CSQ` for VEP-style consequence annotations.
- `--annotation-field ANN` for SnpEff-style consequence annotations.
- `--annotation-field SYMBOL` or another simple INFO key where values are gene
  symbols.
- `--annotation-field auto`, the default, which tries `CSQ`, `ANN`, then simple
  gene-symbol keys such as `SYMBOL`, `GENE`, `Gene`, or `HUGO`.

For `CSQ` and `ANN`, parse the header metadata to locate the gene-symbol and
consequence fields instead of assuming fixed pipe positions. If a file lacks
parseable annotation metadata, fail in strict mode and otherwise skip affected
records with a warning in the report.

Mutation calls should require both:

1. A panel gene assignment.
2. A protein-altering consequence.

Default protein-altering consequence terms should include at least:

- `missense_variant`
- `stop_gained`
- `stop_lost`
- `start_lost`
- `frameshift_variant`
- `splice_acceptor_variant`
- `splice_donor_variant`
- `protein_altering_variant`
- `inframe_insertion`
- `inframe_deletion`

The list should be configurable through `--mutation-effects`, because upstream
annotation systems and model owners may use different consequence policies.

## Copy-Number Classification

The converter should keep small sequence deletions separate from copy-number
deletions in the internal representation:

- Small SNPs and indels with protein-altering consequences set
  the `mutation` feature channel.
- Structural or copy-number deletions set the `copy_number_deletion` feature
  channel.
- Structural or copy-number amplifications set the
  `copy_number_amplification` feature channel.

Copy-number event detection should use this priority order:

1. If sample-level `FORMAT/CN` is present, classify per sample from copy number:
   deletion when `CN < --cn-neutral-low`, amplification when
   `CN > --cn-neutral-high`.
2. Else if `INFO/SVTYPE` or symbolic `ALT` says `DEL` and the sample genotype is
   non-reference, set deletion.
3. Else if `INFO/SVTYPE` or symbolic `ALT` says `DUP` and the sample genotype is
   non-reference, set amplification.
4. Else if `SVTYPE=CNV` has no sample copy number, skip by default because the
   direction is ambiguous.

Default thresholds should be conservative and configurable:

```text
--cn-neutral-low 1.5
--cn-neutral-high 2.5
```

For integer copy-number calls this means `0` or `1` is deletion, `2` is neutral,
and `3+` is amplification. Tumor purity, ploidy, and caller-specific continuous
copy-number values vary, so these thresholds must be command line options.

## Output Files

Given `N` output samples and `G` active panel genes, the shared internal result
is three binary matrices with rows in output sample order and columns in active
panel order:

- `mutation`
- `copy_number_amplification`
- `copy_number_deletion`

Each matrix value is binary. Multiple records for the same sample and gene are
combined with logical OR, so a gene remains `1` once any qualifying event is
found.

### AIxPORT Output Profile

- `gene2ind.txt`: copied from the active panel in panel order.
- `cell2ind.txt`: `N` tab-delimited rows, zero-based in VCF sample order after
  filtering and sample mapping.
- `cell2mutation.txt`: `N` comma-delimited rows and `G` columns.
- `cell2cnamplification.txt`: `N` comma-delimited rows and `G` columns.
- `cell2cndeletion.txt`: `N` comma-delimited rows and `G` columns.

### MutationProjector Output Profile

Write tab-delimited files at the output dataset root:

- `mut.txt`: first column `sample`, followed by one column per active panel
  gene containing the internal `mutation` matrix.
- `cna.txt`: first column `sample`, followed by one column per active panel
  gene containing the internal `copy_number_amplification` matrix.
- `cnd.txt`: first column `sample`, followed by one column per active panel
  gene containing the internal `copy_number_deletion` matrix.
- `covariates.txt`: copied from `--covariates` when provided, or generated
  from a documented defaults policy.
- `outcomes.txt`: copied from `--outcomes` when provided, or generated from a
  documented defaults policy for prediction-only runs.

The first implementation should require `--covariates` and `--outcomes` for
`--output-profile mutationprojector` unless explicit placeholder flags are set,
for example `--default-covariates` and `--default-outcomes`. Placeholder
generation must be recorded in `conversion_report.json` because those files
affect model behavior but are not derivable from VCF.

Additional audit files:

- `conversion_report.json`: input paths, panel ID, sample counts, gene counts,
  records read, records used, records skipped by reason, and command options.
- `variants_used.tsv`: one row per VCF record/sample/gene event that set an
  output bit.
- `variants_skipped.tsv`: skipped records with reason codes such as
  `non_panel_gene`, `no_gene_annotation`, `filtered_record`,
  `reference_genotype`, `missing_genotype`, `unsupported_cnv`, or
  `non_protein_altering`.

## Internal Design

Add a new module:

```text
aixport/vcf2inputs.py
```

Suggested classes:

- `VCFToInputsTool(BaseCommandLineTool)`: command wrapper, argument parsing,
  RO-Crate lifecycle, and output writing.
- `GenePanel`: loads and validates `gene2ind.txt`, resolves aliases, and maps
  gene symbols to column indices.
- `SampleMap`: validates optional sample ID remapping and preserves output row
  order.
- `VCFAnnotationExtractor`: extracts panel gene symbols and consequences from
  `INFO`.
- `VariantClassifier`: decides whether a record/sample/gene event is mutation,
  copy-number deletion, copy-number amplification, or skipped.
- `FeatureMatrixBuilder`: owns the three internal binary matrices and ORs
  events into the correct sample and gene positions.
- `OutputWriter`: abstract writer interface for profile-specific file layouts.
- `AIxPORTOutputWriter`: writes `gene2ind.txt`, `cell2ind.txt`, and the three
  AIxPORT matrix files.
- `MutationProjectorOutputWriter`: writes `mut.txt`, `cna.txt`, `cnd.txt`,
  and validates or materializes `covariates.txt` and `outcomes.txt`.
- `ConversionReport`: accumulates counters and writes JSON/TSV audit files.

Use `pysam.VariantFile` for VCF parsing if adding a dependency is acceptable.
It handles VCF headers, genotype parsing, multi-sample records, and compressed
VCFs more reliably than a custom parser. If dependency growth is a concern, a
minimal parser can be implemented for plain text VCFs, but that should be a
deliberate tradeoff because genotype and INFO parsing edge cases are common.

Command registration steps:

1. Add `VCFToInputsTool` in `aixport/vcf2inputs.py`.
2. Import it in `aixport/aixportcmd.py`.
3. Call `VCFToInputsTool.add_subparser(subparsers)`.
4. Add a dispatch branch for `VCFToInputsTool.COMMAND`.
5. Add package data configuration so bundled gene panels are included in source
   and wheel distributions.
6. Add docs in `docs/usage.rst` and `docs/inputs.rst` after implementation.

## High-Level Algorithm

```text
load active GenePanel
open VCF
derive output samples from VCF header, --sample, and --sample-map
select OutputWriter from --output-profile
initialize mutation, copy_number_amplification, and copy_number_deletion
matrices with zeros

for each VCF record:
    if record FILTER is not PASS or . and --include-filtered is false:
        record skipped filtered_record
        continue

    extract gene/consequence annotations
    resolve genes to active panel columns
    if no panel genes:
        record skipped non_panel_gene or no_gene_annotation
        continue

    for each selected sample:
        parse genotype and optional sample fields such as GQ, DP, CN
        if genotype is missing or reference:
            skip sample event
            continue
        if sample quality filters fail:
            skip sample event
            continue

        classify event as mutation, copy_number_deletion,
        copy_number_amplification, or skipped
        set matrix[sample_index][gene_index] = 1 for each classified event
        append used event to variants_used.tsv

write profile-specific files through OutputWriter
write report and skipped-event audit
finalize RO-Crate
return 0
```

## Testing Plan

Add unit tests with small synthetic VCF fixtures rather than relying on large
real callsets:

- Gene panel loading rejects duplicate genes, duplicate indices, and
  noncontiguous indices.
- `cell2ind.txt` preserves VCF sample order and applies `--sample-map`.
- Non-reference genotypes set mutation bits; reference and missing genotypes do
  not.
- Phased (`0|1`) and unphased (`0/1`) genotypes behave the same.
- Multi-allelic genotypes use the correct alternate allele annotations when
  available.
- `FILTER` handling skips failed records by default and includes them with
  `--include-filtered`.
- `CSQ`, `ANN`, and simple gene-symbol INFO fields are parsed correctly.
- Synonymous or non-coding consequences do not set `cell2mutation.txt` by
  default.
- `FORMAT/CN`, `SVTYPE=DEL`, and `SVTYPE=DUP` set the expected copy-number
  matrices.
- `SVTYPE=CNV` without direction is skipped and reported.
- Output matrices have exactly one row per selected sample and one column per
  active gene.
- The command creates an RO-Crate output directory, task start/finish JSON, the
  five expected feature files, and conversion audit files.
- `--output-profile aixport` writes comma-delimited matrix files matching the
  current AIxPORT contract.
- `--output-profile mutationprojector` writes tab-delimited `mut.txt`,
  `cna.txt`, and `cnd.txt` with a `sample` first column and gene columns in the
  `mutationprojector_mskimpact468` panel order.
- MutationProjector output fails when `--covariates` or `--outcomes` are
  missing unless explicit placeholder flags are passed.
- MutationProjector output copies supplied covariate and outcome files without
  silently reordering or dropping samples; mismatches with generated genomic
  samples should fail with a clear error.

Integration tests should run through `aixportcmd.py vcf2inputs` using a tiny
two-sample VCF and a tiny custom `gene2ind.txt`. A separate fixture can assert
that the bundled `nest_vnn_718` panel has 718 genes, but the functional tests do
not need all 718 columns.

## Expansion Path

The key expansion point is the gene panel registry. Adding a new model panel
should require adding a new panel directory and selecting it with
`--gene-panel`, not editing converter logic.

Future extensions can include:

- Coordinate-based gene assignment from a BED/GTF file for VCFs without gene
  annotations.
- Additional annotation extractors for caller-specific INFO fields.
- Separate mutation and CN VCF inputs if a workflow emits SNV/indel calls and
  CN calls as different files.
- Optional generation of a complete prediction RO-Crate by copying a provided
  `test_data.txt`.
- Additional output profiles for models with matrix layouts different from
  AIxPORT and MutationProjector.
- More advanced copy-number rules that account for tumor ploidy, purity, or
  model-specific thresholds.

## Recommended First Implementation Scope

Implement the smallest robust version:

1. New `vcf2inputs` command with RO-Crate output.
2. `--output-profile` with `aixport` and `mutationprojector` writers.
3. Bundled `nest_vnn_718` gene panel copied from the canonical NeST-VNN
   `gene2ind.txt` order.
4. Bundled `mutationprojector_mskimpact468` panel matching MutationProjector's
   sorted post-alias gene order.
5. Optional `--gene2ind` for tests and future panels.
6. `pysam`-based parsing of `.vcf` and `.vcf.gz`.
7. `CSQ`, `ANN`, and simple gene-symbol INFO extraction.
8. Binary OR matrix generation for mutation, amplification, and deletion.
9. JSON/TSV audit outputs.
10. Focused unit tests and one CLI integration test per output profile.

This scope satisfies the immediate requirement while preserving a clean path for
additional genes, model panels, annotation formats, copy-number policies, and
model-specific output layouts.
