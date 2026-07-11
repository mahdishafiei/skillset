---
name: abstar
description: Annotate antibody (BCR/immunoglobulin) or TCR sequences and get VDJ germline gene assignment, gene usage, CDR3, isotype, and somatic hypermutation. Use whenever the user drops in one or more nucleotide sequences (pasted, a FASTA/FASTQ file, or a folder) and asks to annotate them, identify the V/D/J/C genes, get CDR3/junction, measure SHM/mutation, or summarize gene usage / repertoire composition. Triggers include "/abstar", "annotate this sequence", "what V gene / VDJ genes is this", "germline assignment", "gene usage", "CDR3", "isotype", "how mutated is this antibody", or pasting antibody/TCR DNA.
---

# abstar — antibody / TCR annotation & gene usage

Runs the locally-installed **abstar** (brineylab VDJ annotation) on whatever sequences the
user provides, then returns per-sequence gene calls plus a gene-usage summary and charts,
and saves the full AIRR/Parquet output to a run folder.

## Core rule (do not break)

**Always run the script below. Never infer, guess, or "read off" gene calls, CDR3s, or
mutations yourself.** abstar does the immunogenetics; your job is to run it and present the
result. If abstar can't be run, say so — don't substitute a guess.

## How to run

**1. Put the input in a file.** If the user pasted sequence(s), write them to a FASTA file
in the scratchpad (one `>name` header per sequence; if they pasted bare DNA, invent names).
If they gave a file or folder path, use it directly. Very short single sequences can instead
be passed inline with `--seq`.

**2. Run the launcher.** It finds the abstar venv automatically (set `ABSTAR_HOME` if
abstar lives somewhere unusual) and runs everything under it:

```bash
bash ~/.claude/skills/abstar/scripts/run.sh \
  --input "<path-to-fasta-or-folder>" \
  --name "<short_run_name>" \
  --receptor bcr        # bcr (antibodies, default) or tcr
```

Options: `--germline-database` (`human` default; also `macaque`, `balbc`, `c57bl6`,
`human+c57bl6` for BCR; `human` for TCR), `--top N` (genes per chart, default 20),
`--no-charts`, `--outdir` (defaults to the Drive `abstar_runs/` folder).

**3. Present the result.** The script prints a human summary and a JSON block between
`=== ABSTAR SUMMARY (JSON) ===` markers. Relay the key numbers (sequence count,
% productive, loci, top V/J genes, isotypes, mean SHM, CDR3 length), then **show the charts
inline** by Read-ing the PNGs in `<run_dir>/charts/`, and point the user to the saved run
folder. For a single sequence, just give its locus, V/D/J/C call, CDR3 (aa), productivity,
and SHM%.

## Amino-acid input (automatic)

abstar only accepts **nucleotide** sequences. If the input is **amino acid** (detected
automatically), the wrapper reverse-translates it to nucleotide with
[`dnachisel.reverse_translate(..., randomize_codons=True)`](https://github.com/Edinburgh-Genome-Foundry/DnaChisel)
(reading via `abutils.io.read_fasta`) before running abstar — no action needed from you.
Detection is per-sequence, so mixed aa/nt input works.

When this happens, tell the user: **gene calls, regions, and CDR3 (aa) are valid, but
nucleotide-level SHM / mutation counts are NOT meaningful** (the codons were invented by the
back-translation). The script already prints this caveat and marks SHM as `n/a`.

## What gets saved (per run)

A timestamped folder under `06_VS_code/abstar_runs/` containing:
`airr/*.tsv` (all 147 fields), `parquet/*.parquet`, `gene_usage.csv`, `summary.json`,
`report.md`, and `charts/` (V-gene usage, J-gene usage, isotype/locus, CDR3-length).

## Building on top of it

The AIRR TSV / Parquet and `summary.json` are the hooks for follow-ups the user may ask for:
compare gene usage across runs, filter by productivity / CDR3 length / specific V gene,
plot custom charts (use the `dataviz` skill for bespoke figures), match CDR3s to known
antibodies, or feed results into downstream clustering/phylogenetics (abutils is installed).
Read `references/output_fields.md` for the full field list before doing field-level work.

## Environment notes

- Requires a working abstar install with a `.venv` (see the skill README). The launcher
  auto-detects it; override with `ABSTAR_HOME=/path/to/abstar`. Results default to
  `<ABSTAR_HOME>/../abstar_runs`; override with `ABSTAR_RESULTS_DIR`.
- The script auto-reapplies the abutils "spaces in path" patch if a venv rebuild wiped it,
  so it stays robust. It prints a note when it does.
- Runs from a real `.py` file (macOS multiprocessing uses spawn) — don't reimplement it as a
  `python - <<HEREDOC`.
