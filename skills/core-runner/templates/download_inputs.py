#!/usr/bin/env python
"""download_inputs.py — pull inputs/weights from a source (HuggingFace shown) instead of hand-copying.

Run once on a machine with internet (login node is fine); then stage_inputs.sh syncs them to object
storage. Prefer public repos + weights-only files, and stage a tokenizer so compute nodes run offline.
Adapt the repo list / filenames to your job.

Usage: python download_inputs.py [--out <dir>]
"""
import os, argparse
from huggingface_hub import hf_hub_download

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# FILL: map a local name -> (hf_repo_id, [files to pull]). Weights-only keeps it small.
REPOS = {
    # "model_a": ("org/model-a-repo", ["config.json", "model.safetensors"]),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE, "inputs"))
    a = ap.parse_args()
    for name, (repo, files) in REPOS.items():
        dst = os.path.join(a.out, name); os.makedirs(dst, exist_ok=True)
        for fn in files:
            if not os.path.exists(os.path.join(dst, fn)):
                hf_hub_download(repo_id=repo, filename=fn, local_dir=dst)
        print(f"  {name:20s} <- {repo}")
    # tokenizer / other shared assets, so nodes need no internet:
    # from transformers import AutoTokenizer
    # AutoTokenizer.from_pretrained("<tok-id>").save_pretrained(os.path.join(a.out, "tokenizer"))
    print(f"done -> {a.out}   (next: bash stage_inputs.sh)")


if __name__ == "__main__":
    main()
