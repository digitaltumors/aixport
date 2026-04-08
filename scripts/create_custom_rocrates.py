#!/usr/bin/env python3
"""
Create generic per-drug train/test RO-Crates from a tabular response dataset.

Expected output format for each row in train/test_data.txt:
    cell_line<TAB>smiles<TAB>label<TAB>dataset

This script performs a group-aware train/test split per drug so the same
group identifier never appears in both train and test for the same drug.
By default the group column is the same as the cell column.
"""

import argparse
import csv
import json
import math
import os
import random
import shutil
from collections import defaultdict
from datetime import datetime


REQUIRED_SHARED_FILES = [
    "cell2ind.txt",
    "gene2ind.txt",
    "cell2mutation.txt",
    "cell2cndeletion.txt",
    "cell2cnamplification.txt",
]

OPTIONAL_SHARED_FILES = [
    "cell2fusion.txt",
    "cell2expression.txt",
]

ONTOLOGY_CANDIDATES = (
    "ontology.txt",
    "ontology.tsv",
    "hierarchy.txt",
    "hierarchy.cx2",
)


def _safe_slug(name: str) -> str:
    out = name.strip().replace("/", "-").replace("\\", "-")
    out = "_".join(out.split())
    return out


def _detect_delimiter(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tsv", ".txt"):
        return "\t"
    return ","


def _read_delimited_table(path: str):
    delimiter = _detect_delimiter(path)
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        rows = [row for row in reader]
        headers = reader.fieldnames or []
    return headers, rows


def _load_available_cells(cell2ind_path: str):
    allowed = set()
    with open(cell2ind_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            allowed.add(parts[1])
    return allowed


def _copy_shared_files(shared_dir: str, out_dir: str, metadata_template: str = None):
    os.makedirs(out_dir, exist_ok=True)
    missing_required = []
    copied_optional = []

    for fname in REQUIRED_SHARED_FILES:
        src = os.path.join(shared_dir, fname)
        dst = os.path.join(out_dir, fname)
        if not os.path.exists(src):
            missing_required.append(fname)
            continue
        shutil.copy2(src, dst)

    for fname in OPTIONAL_SHARED_FILES:
        src = os.path.join(shared_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_dir, fname))
            copied_optional.append(fname)

    for candidate in ONTOLOGY_CANDIDATES:
        src = os.path.join(shared_dir, candidate)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_dir, os.path.basename(src)))
            copied_optional.append(os.path.basename(src))
            break

    if missing_required:
        raise FileNotFoundError(
            "Missing required shared feature files in {}: {}".format(
                shared_dir, ", ".join(missing_required)
            )
        )

    if metadata_template and os.path.exists(metadata_template):
        shutil.copy2(metadata_template, os.path.join(out_dir, "ro-crate-metadata.json"))

    return copied_optional


def _coerce_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _transform_label(value: float, transform: str, log2_offset: float):
    if transform == "none":
        return value
    if transform == "log2":
        adjusted = value + log2_offset
        if adjusted <= 0:
            return None
        return math.log2(adjusted)
    return value


def _write_metadata(crate_dir, split, drug, source_table, group_col, n_rows, n_groups):
    data_file = f"{split}_data.txt"
    metadata = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            },
            {
                "@id": "./",
                "@type": "Dataset",
                "name": f"{drug} {split} dataset",
                "description": (
                    f"{split.capitalize()} RO-Crate for {drug}. "
                    f"{n_rows} rows across {n_groups} unique {group_col} values. "
                    f"Derived from {os.path.basename(source_table)}."
                ),
                "datePublished": datetime.utcnow().isoformat() + "Z",
                "hasPart": [{"@id": data_file}],
            },
            {
                "@id": data_file,
                "@type": "File",
                "name": data_file,
                "format": "text/tab-separated-values",
                "description": "Columns: cell_line, smiles, label, dataset.",
            },
        ],
    }
    with open(os.path.join(crate_dir, "ro-crate-metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response_table", required=True, help="CSV/TSV with at least drug, cell, and label columns")
    parser.add_argument("--shared_features_dir", required=True, help="Directory containing AIxPORT feature tables")
    parser.add_argument("--output_dir", required=True, help="Output root for per-drug RO-Crates")
    parser.add_argument("--drug_col", default="drug", help="Column name for drug")
    parser.add_argument("--cell_col", default="cell_line", help="Column name for cell/sample identifier")
    parser.add_argument("--group_col", default="", help="Optional split group column; defaults to cell_col")
    parser.add_argument("--label_col", default="auc", help="Column name for response label")
    parser.add_argument("--smiles_col", default="smiles", help="Optional column for SMILES")
    parser.add_argument("--dataset_col", default="dataset", help="Optional source/dataset column")
    parser.add_argument("--dataset_default", default="custom", help="Default dataset tag when dataset_col is missing or blank")
    parser.add_argument("--test_fraction", type=float, default=0.2, help="Test fraction for split by group")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--min_rows_per_drug", type=int, default=20, help="Minimum total rows required per drug")
    parser.add_argument("--min_groups_per_drug", type=int, default=10, help="Minimum unique groups required per drug")
    parser.add_argument("--drugs", default="", help="Optional comma-separated allowlist of drugs")
    parser.add_argument("--label_transform", choices=["none", "log2"], default="none", help="Optional transform on label before writing")
    parser.add_argument("--log2_offset", type=float, default=1.0, help="Offset used when label_transform=log2")
    parser.add_argument("--metadata_template", default="", help="Optional ro-crate-metadata.json template to copy before regeneration")
    args = parser.parse_args()

    if not 0 < args.test_fraction < 1:
        raise ValueError("--test_fraction must be between 0 and 1")

    os.makedirs(args.output_dir, exist_ok=True)
    random.seed(args.seed)

    headers, rows = _read_delimited_table(args.response_table)
    group_col = args.group_col or args.cell_col
    needed = [args.drug_col, args.cell_col, group_col, args.label_col]
    missing_cols = [c for c in needed if c not in headers]
    if missing_cols:
        raise ValueError(f"Missing required columns in response table: {missing_cols}")

    smiles_col = args.smiles_col if args.smiles_col in headers else ""
    dataset_col = args.dataset_col if args.dataset_col in headers else ""

    allowed_cells = _load_available_cells(os.path.join(args.shared_features_dir, "cell2ind.txt"))
    allow_drugs = set()
    if args.drugs.strip():
        allow_drugs = {d.strip().lower() for d in args.drugs.split(",") if d.strip()}

    by_drug = defaultdict(list)
    skipped_bad = 0
    skipped_cell = 0
    for row in rows:
        drug = (row.get(args.drug_col) or "").strip()
        cell = (row.get(args.cell_col) or "").strip()
        group = (row.get(group_col) or "").strip()
        label = _coerce_float(row.get(args.label_col))

        if not drug or not cell or not group or label is None:
            skipped_bad += 1
            continue
        if allow_drugs and drug.lower() not in allow_drugs:
            continue
        if allowed_cells and cell not in allowed_cells:
            skipped_cell += 1
            continue

        label = _transform_label(label, args.label_transform, args.log2_offset)
        if label is None:
            skipped_bad += 1
            continue

        smiles = (row.get(smiles_col) or "").strip() if smiles_col else ""
        if not smiles:
            smiles = drug
        dataset = (row.get(dataset_col) or "").strip() if dataset_col else ""
        if not dataset:
            dataset = args.dataset_default

        by_drug[drug].append((group, cell, smiles, label, dataset))

    copied_optional_once = None
    created = []
    skipped_sparse = []

    for drug, records in sorted(by_drug.items()):
        unique_groups = sorted({r[0] for r in records})
        if len(records) < args.min_rows_per_drug or len(unique_groups) < args.min_groups_per_drug:
            skipped_sparse.append((drug, len(records), len(unique_groups)))
            continue

        random.shuffle(unique_groups)
        n_test_groups = max(1, int(round(len(unique_groups) * args.test_fraction)))
        n_test_groups = min(n_test_groups, len(unique_groups) - 1)
        train_groups = set(unique_groups[n_test_groups:])
        test_groups = set(unique_groups[:n_test_groups])
        if not train_groups or not test_groups:
            skipped_sparse.append((drug, len(records), len(unique_groups)))
            continue

        train_rows = [r for r in records if r[0] in train_groups]
        test_rows = [r for r in records if r[0] in test_groups]
        if not train_rows or not test_rows:
            skipped_sparse.append((drug, len(records), len(unique_groups)))
            continue

        drug_slug = _safe_slug(drug)
        base_dir = os.path.join(args.output_dir, drug_slug)
        train_crate = os.path.join(base_dir, f"{drug_slug}_train_rocrate")
        test_crate = os.path.join(base_dir, f"{drug_slug}_test_rocrate")

        copied_optional_train = _copy_shared_files(args.shared_features_dir, train_crate, args.metadata_template or None)
        copied_optional_test = _copy_shared_files(args.shared_features_dir, test_crate, args.metadata_template or None)
        if copied_optional_once is None:
            copied_optional_once = sorted(set(copied_optional_train + copied_optional_test))

        with open(os.path.join(train_crate, "train_data.txt"), "w") as f:
            for _group, cell, smiles, label, dataset in train_rows:
                f.write(f"{cell}\t{smiles}\t{label:.8g}\t{dataset}\n")

        with open(os.path.join(test_crate, "test_data.txt"), "w") as f:
            for _group, cell, smiles, label, dataset in test_rows:
                f.write(f"{cell}\t{smiles}\t{label:.8g}\t{dataset}\n")

        _write_metadata(train_crate, "train", drug, args.response_table, group_col, len(train_rows), len(train_groups))
        _write_metadata(test_crate, "test", drug, args.response_table, group_col, len(test_rows), len(test_groups))

        created.append({
            "drug": drug,
            "drug_slug": drug_slug,
            "rows": len(records),
            "groups": len(unique_groups),
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
        })

    print(f"Input rows: {len(rows)}")
    print(f"Skipped bad/missing rows: {skipped_bad}")
    print(f"Skipped rows not in cell2ind: {skipped_cell}")
    if copied_optional_once:
        print("Copied optional shared files: " + ", ".join(copied_optional_once))

    print("\nCreated drug rocrates:")
    for rec in created:
        print(
            f"  {rec['drug']} ({rec['drug_slug']}): total={rec['rows']} rows, "
            f"{rec['groups']} groups, train={rec['train_rows']}, test={rec['test_rows']}"
        )

    if skipped_sparse:
        print("\nSkipped due to insufficient data:")
        for drug, n_rows, n_groups in skipped_sparse:
            print(f"  {drug}: rows={n_rows}, groups={n_groups}")

    print(f"\nDone. Output written to: {args.output_dir}")


if __name__ == "__main__":
    main()
