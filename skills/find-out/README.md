# find-out

> Deep, PhD-level research on any subject → a cited **PDF** + a two-host **audio podcast** + a transcript.

`/find-out` takes a subject you name, spins up **parallel research agents** to comb the web and academic databases (PubMed, bioRxiv, arXiv, …), traces everything back to primary sources, and then produces three self-contained deliverables:

1. **A polished, cited PDF** — TL;DR, background, the problem it solves, deep mechanics, applications, key **figures reproduced from the source papers**, honest limitations, and an annotated bibliography.
2. **A NotebookLM-style audio overview** — two hosts (neural voices) having a natural ~6–12 minute conversation that teaches the topic.
3. **A transcript** of the audio.

Everything lands in one folder per subject: `~/find-out/<subject>/`.

## Usage

```
/find-out <subject> — <who you are + why you want it>
```

The part after the `—` tunes the depth and framing to you. Examples:

```
/find-out spatial transcriptomics — I'm a molecular biologist starting a project and need methods + current applications
/find-out the paper "Attention Is All You Need" — explain transformers to me from scratch
/find-out RNA velocity as a single-cell method, PhD level
```

## Requirements

| Tool | Purpose | Install (macOS) |
|------|---------|-----------------|
| `pandoc` + LaTeX (`xelatex`) | build the PDF | `brew install pandoc`; TinyTeX / MacTeX / TeX Live |
| `ffmpeg` | stitch the audio | `brew install ffmpeg` |
| `python3` + `matplotlib` | generate figures | `pip install matplotlib` |
| `edge-tts` | neural TTS voices (free, no API key, needs internet) | `pip install edge-tts` |

If `edge-tts` can't reach the network, the skill falls back to the offline macOS `say` voices (lower quality) so you still get audio.

## Configuration

By default, output goes to `~/find-out/`. To change the location, edit the library-root path in **Step 5 / Step 6** of [`SKILL.md`](SKILL.md).

## Notes

- Neural audio is generated on Microsoft's servers via `edge-tts`, so the spoken script text is sent there — fine for public topics, worth knowing for anything sensitive.
- Citations and benchmark numbers are drawn from primary sources; preprint (non-peer-reviewed) claims are flagged as such in the document.
