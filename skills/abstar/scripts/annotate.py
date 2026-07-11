#!/usr/bin/env python
"""
abstar skill — annotate antibody/TCR sequences and summarize gene usage.

Runs the local abstar install on whatever sequences you give it (pasted text,
a FASTA/FASTQ file, or a directory), then writes AIRR + Parquet output, a
gene-usage summary, and publication-quality charts into a timestamped run folder.

MUST be run with the abstar venv's python (it imports abstar/abutils/polars/matplotlib):

    "$ABSTAR_HOME/.venv/bin/python" annotate.py --input <path-or-fasta> --name <name>

Everything the skill needs to relay to the user is printed to stdout between the
`=== ABSTAR SUMMARY (JSON) ===` markers (machine-readable) and a human summary above it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# locations — auto-detected so the skill is portable; override with env vars.
#   ABSTAR_HOME        : the abstar checkout that holds .venv (default: derived
#                        from the running interpreter, <home>/.venv/bin/python)
#   ABSTAR_RESULTS_DIR : where run folders go (default: <ABSTAR_HOME>/../abstar_runs)
# ---------------------------------------------------------------------------
def _abstar_home() -> str:
    env = os.environ.get("ABSTAR_HOME")
    if env and os.path.isdir(env):
        return env
    # annotate.py is launched by <home>/.venv/bin/python -> derive <home>
    return os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))


def _default_results_dir() -> str:
    env = os.environ.get("ABSTAR_RESULTS_DIR")
    if env:
        return env
    return os.path.join(os.path.dirname(_abstar_home()), "abstar_runs")

# clean, colorblind-friendly palette
PRIMARY = "#4C78A8"
CATEGORICAL = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2", "#FF9DA6", "#9D755D"]


# ---------------------------------------------------------------------------
# environment self-healing: abutils runs mmseqs via shell without quoting, so a
# space in the install path (Google Drive "My Drive") breaks it. Re-apply the
# shlex.quote fix if a venv rebuild / abutils upgrade ever wiped it.
# ---------------------------------------------------------------------------
def ensure_abutils_patch() -> str | None:
    import abutils

    search_py = os.path.join(os.path.dirname(abutils.__file__), "tools", "search.py")
    try:
        with open(search_py, "r") as f:
            src = f.read()
    except OSError:
        return None
    if "shlex.quote(mmseqs_bin)" in src:
        return None  # already patched
    if " " not in search_py:
        return None  # no space in path -> patch not needed
    patched = src
    if "import shlex" not in patched:
        patched = patched.replace(
            "import subprocess as sp", "import shlex\nimport subprocess as sp", 1
        )
    old = (
        'mmseqs_cmd = f"{mmseqs_bin} easy-search {query} {target} '
        '{output_path} {temp_directory} --search-type {search_type}"'
    )
    new = (
        "mmseqs_cmd = (\n"
        '        f"{shlex.quote(mmseqs_bin)} easy-search"\n'
        '        f" {shlex.quote(query)} {shlex.quote(target)} {shlex.quote(output_path)}"\n'
        '        f" {shlex.quote(temp_directory)} --search-type {search_type}"\n'
        "    )"
    )
    if old in patched:
        patched = patched.replace(old, new, 1)
    if patched != src:
        try:
            with open(search_py, "w") as f:
                f.write(patched)
            return search_py
        except OSError:
            return None
    return None


# ---------------------------------------------------------------------------
# input handling
# ---------------------------------------------------------------------------
_NUC = set("ACGTUNRYSWKMBDHVacgtunryswkmbdhv-.")


def materialize_input(raw_text: str, run_dir: str) -> str:
    """Turn pasted sequence text (FASTA or bare sequences) into a .fasta path."""
    text = raw_text.strip()
    dest = os.path.join(run_dir, "input.fasta")
    if text.startswith(">"):
        with open(dest, "w") as f:
            f.write(text if text.endswith("\n") else text + "\n")
        return dest
    # treat as one-or-more bare sequences (whitespace/newline separated)
    tokens = [t for t in re.split(r"\s+", text) if t]
    seqs = [t for t in tokens if set(t) <= _NUC and len(t) >= 20]
    if not seqs:
        # last resort: whole thing as one sequence
        seqs = ["".join(tokens)]
    with open(dest, "w") as f:
        for i, s in enumerate(seqs, 1):
            f.write(f">seq{i}\n{s}\n")
    return dest


def resolve_input(args, run_dir: str) -> str:
    if args.input:
        if os.path.exists(args.input):
            return os.path.abspath(args.input)
        # not a path -> treat the string as sequence text
        return materialize_input(args.input, run_dir)
    if args.seq:
        return materialize_input(args.seq, run_dir)
    data = sys.stdin.read()
    if not data.strip():
        sys.exit("no input provided (use --input PATH, --seq TEXT, or pipe FASTA on stdin)")
    return materialize_input(data, run_dir)


# ---------------------------------------------------------------------------
# amino-acid input -> nucleotide (abstar only accepts nucleotide)
# ---------------------------------------------------------------------------
def _is_protein(seq: str, thresh: float = 0.9) -> bool:
    """True if the sequence looks like protein rather than nucleotide."""
    s = "".join(seq.split()).upper().replace("-", "").replace(".", "").replace("*", "")
    if len(s) < 3:
        return False
    ntc = sum(c in "ACGTUN" for c in s)
    return (ntc / len(s)) < thresh  # <90% ACGTUN => amino acid


def prepare_nucleotide_input(input_path: str, run_dir: str):
    """abstar needs nucleotide. If the input holds amino-acid sequences, reverse-
    translate them with dnachisel (randomized codons) so abstar can assign genes.
    Returns (path_to_use, n_backtranslated)."""
    import abutils

    if os.path.isdir(input_path):
        return input_path, 0  # directory batch: assume nucleotide reads
    try:
        fmt = abutils.io.determine_fastx_format(input_path)
    except Exception:
        fmt = "fasta"
    if fmt == "fastq":
        return input_path, 0  # sequencing reads are nucleotide

    seqs = list(abutils.io.read_fasta(input_path))
    if not seqs or not any(_is_protein(s.sequence) for s in seqs):
        return input_path, 0

    import dnachisel as dc  # published: DnaChisel reverse_translate

    out_path = os.path.join(run_dir, "input_nt.fasta")
    n = 0
    with open(out_path, "w") as f:
        for s in seqs:
            seq = s.sequence
            if _is_protein(seq):
                aa = "".join(seq.upper().split()).replace("-", "").replace(".", "").replace("*", "")
                nt = dc.reverse_translate(aa, randomize_codons=True)
                n += 1
            else:
                nt = seq
            f.write(f">{s.id}\n{nt}\n")
    return out_path, n


# ---------------------------------------------------------------------------
# summarization
# ---------------------------------------------------------------------------
def load_airr(run_dir: str):
    import polars as pl

    tsvs = sorted(glob.glob(os.path.join(run_dir, "airr", "*.tsv")))
    if not tsvs:
        return None
    frames = [pl.read_csv(t, separator="\t", infer_schema_length=0) for t in tsvs]  # all Utf8
    df = pl.concat(frames, how="diagonal_relaxed") if len(frames) > 1 else frames[0]
    return df


def _clean_series(df, col):
    import polars as pl

    if col not in df.columns:
        return None
    s = df.select(pl.col(col)).to_series()
    s = s.replace("", None)
    return s.drop_nulls()


def _usage(df, col, top=None):
    """Return list of (value, count, percent) sorted by count desc."""
    s = _clean_series(df, col)
    if s is None or s.len() == 0:
        return []
    total = s.len()
    vc = s.value_counts(sort=True)
    name = vc.columns[0]
    out = []
    for row in vc.iter_rows(named=True):
        out.append((row[name], int(row["count"]), round(100.0 * row["count"] / total, 2)))
    return out[:top] if top else out


def _gene_col(df, seg):
    """Prefer the allele-free *_gene column; fall back to *_call (strip allele)."""
    import polars as pl

    gcol, ccol = f"{seg}_gene", f"{seg}_call"
    if gcol in df.columns and _clean_series(df, gcol) is not None and _clean_series(df, gcol).len():
        return gcol
    if ccol in df.columns:
        # derive allele-free gene into a temp column
        df2 = df.with_columns(
            pl.col(ccol).str.replace_all(r"\*.*$", "").str.replace_all(r",.*$", "").alias(f"_{seg}_gene_tmp")
        )
        return df2, f"_{seg}_gene_tmp"
    return None


def compute_summary(df, run_dir):
    import polars as pl

    n = df.height
    summary = {"n_sequences": n}

    # productivity
    if "productive" in df.columns:
        prod = df.select(
            (pl.col("productive").str.to_lowercase().is_in(["true", "t", "1"])).sum()
        ).item()
        summary["n_productive"] = int(prod)
        summary["pct_productive"] = round(100.0 * prod / n, 1) if n else 0.0

    # loci
    summary["loci"] = {v: c for v, c, _ in _usage(df, "locus")}

    # V / J / D gene usage
    def usage_for(seg, top=None):
        res = _gene_col(df, seg)
        if res is None:
            return []
        if isinstance(res, tuple):
            d2, col = res
            return _usage(d2, col, top=top)
        return _usage(df, res, top=top)

    summary["v_gene_usage"] = usage_for("v")
    summary["j_gene_usage"] = usage_for("j")
    summary["d_gene_usage"] = usage_for("d")
    summary["n_unique_v_genes"] = len(summary["v_gene_usage"])
    summary["n_unique_j_genes"] = len(summary["j_gene_usage"])

    # isotype / constant region
    summary["isotype_usage"] = _usage(df, "c_call")

    # CDR3 length
    if "cdr3_length" in df.columns:
        lens = df.select(pl.col("cdr3_length").cast(pl.Int64, strict=False)).to_series().drop_nulls()
        if lens.len():
            summary["cdr3_length"] = {
                "mean": round(lens.mean(), 1),
                "median": float(lens.median()),
                "min": int(lens.min()),
                "max": int(lens.max()),
            }

    # SHM (from V germline identity)
    if "v_identity" in df.columns:
        vid = df.select(pl.col("v_identity").cast(pl.Float64, strict=False)).to_series().drop_nulls()
        if vid.len():
            mx = vid.max()
            pct = vid * (100.0 if mx <= 1.5 else 1.0)  # normalize fraction -> percent
            summary["mean_v_germline_identity_pct"] = round(pct.mean(), 2)
            summary["mean_v_shm_pct"] = round(100.0 - pct.mean(), 2)

    # write machine-readable gene-usage table (long format)
    rows = []
    for cat, items in (
        ("v_gene", summary["v_gene_usage"]),
        ("j_gene", summary["j_gene_usage"]),
        ("d_gene", summary["d_gene_usage"]),
        ("isotype", summary["isotype_usage"]),
    ):
        for value, count, pct in items:
            rows.append({"category": cat, "value": value, "count": count, "percent": pct})
    if rows:
        pl.DataFrame(rows).write_csv(os.path.join(run_dir, "gene_usage.csv"))

    return summary


# ---------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------
def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 140,
            "savefig.bbox": "tight",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "axes.axisbelow": True,
            "axes.titleweight": "bold",
            "figure.autolayout": True,
        }
    )
    return plt


def make_charts(summary, df, charts_dir, top=20):
    os.makedirs(charts_dir, exist_ok=True)
    plt = _style()
    made = []

    def hbar(items, title, fname, color=PRIMARY):
        if not items:
            return
        items = items[:top][::-1]
        labels = [i[0] for i in items]
        pcts = [i[2] for i in items]
        fig, ax = plt.subplots(figsize=(7.5, max(2.5, 0.34 * len(items) + 1.2)))
        ax.barh(labels, pcts, color=color)
        ax.set_xlabel("% of sequences")
        ax.set_title(title)
        for y, p in enumerate(pcts):
            ax.text(p, y, f" {p:.1f}", va="center", fontsize=9, color="#333")
        p = os.path.join(charts_dir, fname)
        fig.savefig(p)
        plt.close(fig)
        made.append(p)

    hbar(summary.get("v_gene_usage", []), "V-gene usage", "v_gene_usage.png")
    hbar(summary.get("j_gene_usage", []), "J-gene usage", "j_gene_usage.png", color="#54A24B")

    # isotype / locus categorical bar
    iso = summary.get("isotype_usage") or [(k, v, round(100 * v / summary["n_sequences"], 1)) for k, v in summary.get("loci", {}).items()]
    if iso:
        iso = iso[:top]
        fig, ax = plt.subplots(figsize=(max(4, 0.7 * len(iso) + 1.5), 3.6))
        ax.bar([i[0] for i in iso], [i[2] for i in iso], color=CATEGORICAL[: len(iso)])
        ax.set_ylabel("% of sequences")
        ax.set_title("Isotype / locus breakdown")
        ax.tick_params(axis="x", rotation=0)
        p = os.path.join(charts_dir, "isotype_locus.png")
        fig.savefig(p)
        plt.close(fig)
        made.append(p)

    # CDR3 length histogram
    if "cdr3_length" in df.columns:
        import polars as pl

        lens = df.select(pl.col("cdr3_length").cast(pl.Int64, strict=False)).to_series().drop_nulls().to_list()
        if lens:
            fig, ax = plt.subplots(figsize=(7, 3.8))
            lo, hi = min(lens), max(lens)
            ax.hist(lens, bins=range(lo, hi + 2), color=PRIMARY, edgecolor="white", linewidth=0.5)
            ax.set_xlabel("CDR3 length (aa)")
            ax.set_ylabel("sequences")
            ax.set_title("CDR3 length distribution")
            p = os.path.join(charts_dir, "cdr3_length.png")
            fig.savefig(p)
            plt.close(fig)
            made.append(p)

    return made


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# alternative numbering (Kabat / Chothia / IMGT / AHo / Martin) via ANARCI+abnumber
# ---------------------------------------------------------------------------
def _ensure_hmmer_on_path():
    import shutil

    if shutil.which("hmmscan"):
        return
    for d in ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin", "/usr/bin"):
        if os.path.exists(os.path.join(d, "hmmscan")):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return


def compute_numbering(df, run_dir, scheme):
    """Renumber each antibody variable domain in `scheme` (kabat, chothia, imgt, aho,
    martin) using ANARCI via abnumber. Writes numbering_<scheme>.csv (per-sequence
    FR/CDR seqs + lengths) and numbering_<scheme>_positions.tsv (per-residue labels
    like H100A). Returns a small summary dict."""
    _ensure_hmmer_on_path()
    import polars as pl

    try:
        from abnumber import Chain
    except Exception as e:  # anarci/abnumber not installed
        return {"scheme": scheme, "error": f"abnumber/anarci not available: {e}"}

    if "sequence_aa" not in df.columns:
        return {"scheme": scheme, "error": "no sequence_aa column in abstar output"}

    cols = ["fr1", "cdr1", "fr2", "cdr2", "fr3", "cdr3", "fr4",
            "cdr1_len", "cdr2_len", "cdr3_len"]
    rows, pos_rows = [], []
    n_ok = n_fail = 0
    for r in df.select(["sequence_id", "sequence_aa"]).iter_rows(named=True):
        sid, aa = r["sequence_id"], r["sequence_aa"]
        row = {"sequence_id": sid, "numbered": False, "chain_type": None}
        row.update({c: None for c in cols})
        if not aa:
            n_fail += 1
            rows.append(row)
            continue
        try:
            c = Chain(str(aa), scheme=scheme)
        except Exception:
            n_fail += 1
            rows.append(row)
            continue
        n_ok += 1
        row.update({
            "numbered": True, "chain_type": c.chain_type,
            "fr1": c.fr1_seq, "cdr1": c.cdr1_seq, "fr2": c.fr2_seq, "cdr2": c.cdr2_seq,
            "fr3": c.fr3_seq, "cdr3": c.cdr3_seq, "fr4": c.fr4_seq,
            "cdr1_len": len(c.cdr1_seq), "cdr2_len": len(c.cdr2_seq), "cdr3_len": len(c.cdr3_seq),
        })
        rows.append(row)
        for pos, resi in c:
            pos_rows.append({"sequence_id": sid, "position": str(pos),
                             "residue": resi, "region": pos.get_region()})

    if rows:
        pl.DataFrame(rows).write_csv(os.path.join(run_dir, f"numbering_{scheme}.csv"))
    if pos_rows:
        pl.DataFrame(pos_rows).write_csv(
            os.path.join(run_dir, f"numbering_{scheme}_positions.tsv"), separator="\t"
        )

    ok = [r for r in rows if r["numbered"]]
    out = {"scheme": scheme, "n_numbered": n_ok, "n_failed": n_fail}
    if ok:
        c3 = [r["cdr3_len"] for r in ok]
        out["cdr_len_summary"] = {
            "cdr1_mean": round(sum(r["cdr1_len"] for r in ok) / len(ok), 1),
            "cdr2_mean": round(sum(r["cdr2_len"] for r in ok) / len(ok), 1),
            "cdr3_mean": round(sum(c3) / len(c3), 1),
            "cdr3_range": [min(c3), max(c3)],
        }
        if len(ok) == 1:
            e = ok[0]
            out["example"] = {"chain_type": e["chain_type"], "cdr1": e["cdr1"],
                              "cdr2": e["cdr2"], "cdr3": e["cdr3"]}
    return out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def write_report(summary, run_dir, meta, charts):
    lines = [f"# abstar annotation — {meta['name']}", ""]
    lines.append(f"- run: `{os.path.basename(run_dir)}`")
    lines.append(f"- receptor: **{meta['receptor']}**, germline database: **{meta['germline_database']}**")
    lines.append(f"- input type: **{meta.get('input_type', 'nucleotide')}**")
    lines.append(f"- sequences annotated: **{summary['n_sequences']}**")
    if summary.get("_backtranslated"):
        lines.append(
            f"- ⚠️ {summary['_backtranslated']} amino-acid sequence(s) were reverse-translated to "
            "nucleotide (dnachisel, randomized codons). Gene calls, regions and CDR3 (aa) are valid; "
            "**nucleotide-level SHM / mutation counts are not biologically meaningful** for these."
        )
    if "pct_productive" in summary:
        lines.append(f"- productive: **{summary['n_productive']}/{summary['n_sequences']} ({summary['pct_productive']}%)**")
    if summary.get("loci"):
        lines.append("- loci: " + ", ".join(f"{k} ({v})" for k, v in summary["loci"].items()))
    if summary.get("_all_backtranslated"):
        lines.append("- mean V SHM: _n/a (amino-acid input; nt-level mutation not meaningful)_")
    elif "mean_v_shm_pct" in summary:
        lines.append(f"- mean V SHM: **{summary['mean_v_shm_pct']}%** (germline identity {summary['mean_v_germline_identity_pct']}%)")
    if summary.get("cdr3_length"):
        c = summary["cdr3_length"]
        lines.append(f"- CDR3 length (aa): mean {c['mean']}, median {c['median']}, range {c['min']}–{c['max']}")
    lines.append("")

    def table(title, items):
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| gene | count | % |")
        lines.append("|---|---:|---:|")
        for v, c, p in items[:25]:
            lines.append(f"| {v} | {c} | {p} |")
        lines.append("")

    table("Top V genes", summary.get("v_gene_usage", []))
    table("Top J genes", summary.get("j_gene_usage", []))
    if summary.get("isotype_usage"):
        table("Isotypes", summary["isotype_usage"])

    nb = summary.get("_numbering")
    if nb and not nb.get("error"):
        s = nb["scheme"]
        lines.append(f"## {s.capitalize()} numbering (ANARCI/abnumber)")
        lines.append("")
        lines.append(f"Renumbered {nb['n_numbered']}/{nb['n_numbered'] + nb['n_failed']} sequences in the **{s}** scheme.")
        if nb.get("example"):
            e = nb["example"]
            lines.append("")
            lines.append(f"- chain: **{e['chain_type']}**")
            lines.append(f"- {s} CDR1: `{e['cdr1']}`")
            lines.append(f"- {s} CDR2: `{e['cdr2']}`")
            lines.append(f"- {s} CDR3: `{e['cdr3']}`")
        elif nb.get("cdr_len_summary"):
            cs = nb["cdr_len_summary"]
            lines.append(f"- mean CDR lengths: CDR1 {cs['cdr1_mean']}, CDR2 {cs['cdr2_mean']}, CDR3 {cs['cdr3_mean']} (range {cs['cdr3_range'][0]}–{cs['cdr3_range'][1]})")
        lines.append("")

    if charts:
        lines.append("## Charts")
        lines.append("")
        for c in charts:
            lines.append(f"![{os.path.basename(c)}](charts/{os.path.basename(c)})")
        lines.append("")

    lines.append("## Files")
    lines.append("")
    lines.append("- `airr/` — AIRR-format TSV (all 147 fields)")
    lines.append("- `parquet/` — Parquet output")
    lines.append("- `gene_usage.csv` — machine-readable usage table")
    lines.append("- `summary.json` — full summary")
    lines.append("- `charts/` — PNG charts")
    if nb and not nb.get("error"):
        s = nb["scheme"]
        lines.append(f"- `numbering_{s}.csv` — per-sequence {s} FR/CDR sequences & lengths")
        lines.append(f"- `numbering_{s}_positions.tsv` — per-residue {s} position labels (e.g. H100A)")

    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Annotate antibody/TCR sequences with abstar.")
    ap.add_argument("--input", help="FASTA/FASTQ file, directory, or sequence text")
    ap.add_argument("--seq", help="raw sequence or FASTA text (quick single-use)")
    ap.add_argument("--name", default=None, help="run name (default: input name or timestamp)")
    ap.add_argument("--receptor", default="bcr", choices=["bcr", "tcr"])
    ap.add_argument("--germline-database", default="human", dest="germline_database")
    ap.add_argument("--outdir", default=_default_results_dir())
    ap.add_argument("--top", type=int, default=20, help="top N genes to chart")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument(
        "--numbering",
        default="none",
        choices=["none", "kabat", "imgt", "chothia", "aho", "martin"],
        help="also renumber each antibody with this scheme (ANARCI via abnumber)",
    )
    args = ap.parse_args()

    patched = ensure_abutils_patch()

    import abstar  # noqa: after patch

    # run folder
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = args.name
    if not base_name and args.input and os.path.exists(args.input):
        base_name = os.path.splitext(os.path.basename(args.input.rstrip("/")))[0]
    base_name = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name or "sequences")
    run_dir = os.path.join(args.outdir, f"{ts}_{base_name}")
    os.makedirs(run_dir, exist_ok=True)

    input_path = resolve_input(args, run_dir)

    # abstar only accepts nucleotide; auto reverse-translate amino-acid input (dnachisel)
    input_path, n_backtranslated = prepare_nucleotide_input(input_path, run_dir)
    if n_backtranslated:
        print(
            f"note: {n_backtranslated} amino-acid sequence(s) detected -> reverse-translated to "
            "nucleotide (dnachisel, randomized codons) before annotation."
        )

    # run abstar -> writes airr/ + parquet/ into run_dir
    try:
        abstar.run(
            input_path,
            project_path=run_dir,
            receptor=args.receptor,
            germline_database=args.germline_database,
            output_format=["airr", "parquet"],
            copy_inputs_to_project=False,
            verbose=False,
            concise_logging=True,
        )
    except Exception as e:  # abstar's sequential assigner raises on unassignable input
        msg = str(e)
        print("abstar could not annotate the input.")
        if "datatypes of join keys" in msg or ("v_query" in msg and "d_query" in msg):
            print(
                "This is a known abstar type-inference issue that hits small batches (~2-9 "
                "sequences) whose IDs look numeric (e.g. '10E8' parses as a float). Workarounds: "
                "annotate a single sequence, use >=10 sequences, or give the sequences "
                "non-numeric IDs (e.g. prefix each header with a letter)."
            )
        elif "no entry" in msg or "MMseqs" in msg or "mmseqs" in msg:
            print(
                "Likely cause: the sequence(s) are partial (e.g. a V-only fragment with no J "
                "region), too short, or not antibody/TCR reads. abstar needs enough of the "
                "rearrangement to assign both V and J. Check receptor (--receptor bcr|tcr) and "
                "that the input is nucleotide (not amino-acid) sequence."
            )
        else:
            print("error:", msg.strip().splitlines()[-1] if msg.strip() else repr(e))
        print(f"(input saved at: {input_path})")
        sys.exit(0)

    df = load_airr(run_dir)
    if df is None or df.height == 0:
        print("abstar produced no annotated sequences (no identifiable rearrangement).")
        sys.exit(0)

    summary = compute_summary(df, run_dir)
    charts = [] if args.no_charts else make_charts(summary, df, os.path.join(run_dir, "charts"), top=args.top)

    numbering = None
    if args.numbering != "none":
        print(f"computing {args.numbering} numbering (ANARCI/abnumber)...")
        numbering = compute_numbering(df, run_dir, args.numbering)
        summary["_numbering"] = numbering

    meta = {
        "name": base_name,
        "receptor": args.receptor,
        "germline_database": args.germline_database,
        "run_dir": run_dir,
        "input_type": "amino acid (reverse-translated to nucleotide)" if n_backtranslated else "nucleotide",
    }
    all_backtranslated = bool(n_backtranslated) and n_backtranslated == summary["n_sequences"]
    summary["_backtranslated"] = n_backtranslated
    summary["_all_backtranslated"] = all_backtranslated
    summary["_meta"] = meta
    summary["_charts"] = [os.path.relpath(c, run_dir) for c in charts]
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    write_report(summary, run_dir, meta, charts)

    # ---- human-readable stdout ----
    print("=" * 60)
    print(f"abstar: annotated {summary['n_sequences']} sequences  ({args.receptor}, {args.germline_database})")
    if n_backtranslated:
        print(
            f"input: {n_backtranslated} amino-acid sequence(s) back-translated to nucleotide "
            "(gene calls, regions & CDR3-aa are valid; nt-level SHM/mutations are NOT meaningful)"
        )
    if "pct_productive" in summary:
        print(f"productive: {summary['n_productive']}/{summary['n_sequences']} ({summary['pct_productive']}%)")
    if summary.get("loci"):
        print("loci: " + ", ".join(f"{k}={v}" for k, v in summary["loci"].items()))
    if all_backtranslated:
        print("mean V SHM: n/a  (amino-acid input; nt-level mutation not meaningful)")
    elif "mean_v_shm_pct" in summary:
        print(f"mean V SHM: {summary['mean_v_shm_pct']}%  (germline identity {summary['mean_v_germline_identity_pct']}%)")
    if summary.get("cdr3_length"):
        c = summary["cdr3_length"]
        print(f"CDR3 length (aa): mean {c['mean']}, median {c['median']}, range {c['min']}-{c['max']}")
    if summary.get("v_gene_usage"):
        print("top V genes: " + ", ".join(f"{v} {p}%" for v, _, p in summary["v_gene_usage"][:5]))
    if summary.get("j_gene_usage"):
        print("top J genes: " + ", ".join(f"{v} {p}%" for v, _, p in summary["j_gene_usage"][:5]))
    if summary.get("isotype_usage"):
        print("isotypes: " + ", ".join(f"{v} {p}%" for v, _, p in summary["isotype_usage"][:6]))
    if numbering and not numbering.get("error"):
        s = numbering["scheme"]
        total = numbering["n_numbered"] + numbering["n_failed"]
        print(f"{s} numbering: {numbering['n_numbered']}/{total} numbered (ANARCI/abnumber)")
        if numbering.get("example"):
            e = numbering["example"]
            print(f"  {s} CDRs [{e['chain_type']}]: CDR1={e['cdr1']}  CDR2={e['cdr2']}  CDR3={e['cdr3']}")
        elif numbering.get("cdr_len_summary"):
            cs = numbering["cdr_len_summary"]
            print(f"  {s} CDR3 length: mean {cs['cdr3_mean']}, range {cs['cdr3_range'][0]}-{cs['cdr3_range'][1]}")
        print(f"  files: numbering_{s}.csv, numbering_{s}_positions.tsv")
    elif numbering and numbering.get("error"):
        print(f"numbering ({numbering['scheme']}) unavailable: {numbering['error']}")
    if patched:
        print("(note: re-applied abutils spaces-in-path patch)")
    print(f"saved to: {run_dir}")
    print("=" * 60)
    print("=== ABSTAR SUMMARY (JSON) ===")
    print(json.dumps(summary, default=str))
    print("=== END ABSTAR SUMMARY ===")


if __name__ == "__main__":
    main()
