# skillset

A collection of custom [Claude Code](https://claude.com/claude-code) **skills** — reusable, self-contained "protocols" you can drop into any Claude Code setup and trigger with a slash command.

Each skill lives in [`skills/<name>/`](skills) as a single `SKILL.md` (plus a short README). Skills are portable: copy or symlink one into your `~/.claude/skills/` directory and Claude Code picks it up automatically.

## Skills

| Skill | Command | What it does |
|-------|---------|--------------|
| [**find-out**](skills/find-out) | `/find-out <subject>` | Runs an exhaustive, PhD-level literature review on any subject using parallel research agents, then produces a polished, cited **PDF**, a NotebookLM-style two-host **audio podcast** (MP3), and a transcript — all in one self-contained folder. |
| [**abstar**](skills/abstar) | `/abstar` | Annotates antibody (BCR) or TCR sequences with the [brineylab **abstar**](https://github.com/brineylab/abstar) VDJ annotator — per-sequence V/D/J/C gene calls, CDR3, productivity, and SHM — plus a **gene-usage summary** and **charts**, saving the full AIRR/Parquet output to a run folder. |
| [**core_runner**](skills/core_runner) | `/core_runner` | Packages any locally-built compute job into a **self-contained, resumable SLURM bundle** ready to `sbatch` on the brineylab **CoreWeave** clusters (B200 / RTX PRO 6000) — container + mounts, `/tmp` scratch, `s5cmd` object-storage staging, thread caps, `hpc-mid` + the 24 h time cap, and resumable array jobs. |

## Install

Skills are per-user and live in `~/.claude/skills/`.

```bash
git clone git@github.com:mahdishafiei/skillset.git
cd skillset

# symlink every skill (stays in sync as you `git pull`)
./install.sh --all

# …or a single skill
./install.sh find-out

# …or copy manually
cp -r skills/find-out ~/.claude/skills/
```

Then start a new Claude Code session and run the command, e.g. `/find-out`.

## Requirements

Each skill lists its own prerequisites in its README. For **find-out** you'll need:

| Tool | Used for | Install (macOS) |
|------|----------|-----------------|
| `pandoc` + a LaTeX engine | building the PDF | `brew install pandoc` · TinyTeX / MacTeX / TeX Live |
| `ffmpeg` | stitching the audio | `brew install ffmpeg` |
| `python3` + `matplotlib` | generating figures | `pip install matplotlib` |
| `edge-tts` | neural TTS voices | `pip install edge-tts` |

For **abstar** you'll need the [abstar](https://github.com/brineylab/abstar) annotator installed in a Python ≥3.10 virtualenv (`git clone` + `pip install -e .`); MMseqs2 comes bundled. The skill auto-detects the install or you can point it with `ABSTAR_HOME`. See [`skills/abstar/README.md`](skills/abstar/README.md).

## License

[MIT](LICENSE) — free to use, modify, and share.
