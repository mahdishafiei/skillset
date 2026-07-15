#!/usr/bin/env python
"""gen_manifest.py — build configs/manifest.tsv: one line per unit of work for the array job.

Adapt `units()` to your job: enumerate the independent units (e.g. one per input file, per model,
per shard of a big input). Each row's columns become the args the sbatch loop passes to your script.
Keep the header row. The array sbatch reads this and each task processes a strided slice.

Usage: python gen_manifest.py [--out configs/manifest.tsv]
"""
import os, csv, argparse, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def units():
    """Yield one tuple per unit. FILL THIS IN. Columns are up to you (the sbatch parses them)."""
    # --- example A: one unit per input file ---
    for i, f in enumerate(sorted(glob.glob(os.path.join(BASE, "data", "*")))):
        yield (i, os.path.basename(f))
    # --- example B: strided sharding of a big input (uncomment/adapt) ---
    # SEQS_PER_SHARD = 10000
    # for item in items:
    #     n = max(1, math.ceil(count(item) / SEQS_PER_SHARD))
    #     for sh in range(n):
    #         yield (idx, item, n, sh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE, "configs", "manifest.tsv"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    rows = list(units())
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["idx", "arg1"])          # FILL: match your columns / your sbatch parser
        w.writerows(rows)
    print(f"wrote {len(rows)} units -> {a.out}")


if __name__ == "__main__":
    main()
