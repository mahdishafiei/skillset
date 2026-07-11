# abstar

> Drop in antibody/TCR sequences → **VDJ gene calls + gene-usage summary + charts**, saved as AIRR/Parquet.

`/abstar` (or just pasting antibody/TCR DNA and asking to annotate) runs the local
[**abstar**](https://github.com/brineylab/abstar) VDJ annotator on your sequences and returns:

- **Per-sequence annotation** — locus, V/D/J/C gene calls, CDR3 (aa), productivity, and SHM%.
- **Gene-usage summary** — V/J gene frequencies, CDR3-length distribution, isotype breakdown.
- **Publication-quality charts** and the **full AIRR TSV + Parquet** (all 147 fields), saved
  to a timestamped run folder.

The model never guesses gene calls — it always runs abstar and presents the result.

## Input

Pasted sequence(s), a FASTA/FASTQ file, or a whole directory. Nucleotide sequences; BCR
(antibodies, default) or TCR (`--receptor tcr`).

## Usage

```
/abstar        # then paste a sequence or give a FASTA/folder path
```

Under the hood the skill calls its launcher, which finds the abstar venv and runs the
annotator:

```bash
bash ~/.claude/skills/abstar/scripts/run.sh --input <fasta-or-folder> --name <name> \
     [--receptor bcr|tcr] [--germline-database human|macaque|balbc|c57bl6|human+c57bl6] \
     [--top 20] [--no-charts]
```

## Requirements

| Requirement | Notes |
|---|---|
| **abstar** installed in a `.venv` | `git clone git@github.com:brineylab/abstar.git`, then a Python ≥3.10 venv with `pip install -e .`. MMseqs2 is bundled via `abutils`; `parasail` may need `autoconf`/`automake`/`libtool` to build. |
| Python libs (in that venv) | abstar pulls `abutils`, `polars`, `parasail`, `matplotlib`, etc. |

The launcher auto-detects abstar at `~/abstar`, `~/code/abstar`, `~/src/abstar`, or a Google
Drive `…/06_VS_code/abstar`. If it lives elsewhere, set `ABSTAR_HOME=/path/to/abstar`.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ABSTAR_HOME` | auto-detected | the abstar checkout that contains `.venv/bin/python` |
| `ABSTAR_RESULTS_DIR` | `<ABSTAR_HOME>/../abstar_runs` | where run folders are written |

## Output (per run)

`airr/*.tsv`, `parquet/*.parquet`, `gene_usage.csv`, `summary.json`, `report.md`, and
`charts/` (V-gene usage, J-gene usage, isotype/locus, CDR3-length). See
[`references/output_fields.md`](references/output_fields.md) for the full field list.

## Notes

- Partial / V-only fragments (no J region) can't be assigned — the skill reports that clearly
  instead of erroring.
- The wrapper self-heals a "spaces in path" quirk in `abutils` (its shell command isn't
  quoted), so abstar runs fine even from a Google Drive path.
