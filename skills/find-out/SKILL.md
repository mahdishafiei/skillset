---
name: find-out
description: Run an exhaustive, PhD-level literature review and explainer on any scientific subject, term, method, tool, or paper the user names. Search the whole internet plus academic databases, then produce a polished PDF (background, deep applications, the problem it solves, key figures, references, working code) AND a NotebookLM-style two-host audio "podcast" overview. Use when the user runs /find-out or asks to "deeply research", "do a literature review on", "explain everything about", or "find out about" a topic.
---

# Find Out — Deep Literature Review & Explainer

The user runs this to understand a subject *completely*, at the level of a PhD student entering the field. They give you a subject — a scientific notion, a term, a method, a tool, or a specific paper — usually plus some context about why they care. Your job is to search as widely as possible and hand back a self-contained **PDF** plus a two-host **audio overview** that teach them everything they need.

Treat this as if you were writing the review article and the study guide you wish existed for this topic. Be exhaustive. Depth and completeness are the whole point.

## Configure once — where results are saved

Results go into a **library folder**, one **subfolder per subject**. Default library root:

```
$HOME/find-out
```

To change it, edit the path in Step 5 / Step 6 below (or point them at your own directory). Each run creates `<library-root>/<slug>/` (where `<slug>` is the subject in lowercase-with-dashes) and saves that subject's PDF, podcast MP3, and transcript inside it.

## Step 1 — Lock the subject (fast)

Identify **the exact subject**, **the user's context** (their field, why they want it), and **the domain** (biology, chemistry, ML, physics, clinical, …) — the domain decides which databases you hit. Only ask a clarifying question if the subject is genuinely ambiguous (e.g. an acronym with several meanings). Otherwise **proceed immediately** — the user wants this to "just work."

If the subject may not exist or you can't confirm it, do a quick reconnaissance search first and **be honest** if you can't find it — never fabricate a review of something unverifiable.

## Step 2 — Research widely (the core — do not shortcut it)

Cast the widest possible net:

- **Web search / fetch** — general web, blogs, docs, tutorials, textbook chapters, review articles, lecture notes, GitHub repos, talks (read transcripts). Run *many* searches with varied phrasings: the term itself, "X review", "X tutorial", "X vs Y", "how does X work", "X limitations", "X applications", "X original paper", "X explained".
- **Academic databases** when the topic is scientific/biomedical (e.g. PubMed, bioRxiv/medRxiv, arXiv, ChEMBL, ClinicalTrials — whichever are available to you).
- **Primary sources** — always trace back to the foundational/original paper(s) and the most-cited works; read abstracts and, where possible, full text and the authors' code.

**Dispatch parallel research subagents** (one per major facet — history/foundations, mechanism/theory, applications, criticisms/limitations, implementations) and combine their findings. Quality settings (do not compromise):

- Launch subagents with the **highest-capability model** available; never downgrade research agents to a smaller/faster model.
- Give them **no length limit** — instruct each to be exhaustive, read full sources, and write as long a report as the material warrants.
- Prefer **more agents over shallower ones** so each facet goes deep.

Track, as you go: **references** (real, verifiable, with links/DOIs — never invent), **figures** (what each shows + source URL), **code** (canonical implementations, minimal examples), and **numbers** (the concrete facts, equations, parameters, results a PhD student must know).

## Step 3 — Synthesize (rewrite it in your own words)

Understand the material and re-explain it clearly and correctly; reconcile disagreements and flag open questions. Because the deliverable is a **PDF**, make visuals that render in a PDF:

- **Generate real figures** with a short Python/matplotlib script, save them as `.png`, and embed them with `![caption](/abs/path/to/fig.png)`.
- Use **Markdown tables** for structured comparisons.
- Math renders via LaTeX — use `$...$` / `$$...$$` freely. (Pandoc gotcha: a closing `$` must **not** be immediately followed by a digit, e.g. write `$\leq 8$B`, not `$\leq$8B`.)
- Avoid Mermaid diagrams — they don't render in the PDF. Use a generated image, a table, or an ASCII schematic.

## Step 4 — Write the document

One Markdown document, roughly (adapt to the subject — you own the final shape):

1. **Title** · 2. **TL;DR** (3–6 sentences) · 3. **Background & Introduction** (origin, foundations, prerequisites, history) · 4. **The problem it solves** · 5. **How it works / Core concepts** (the deep heart — theory, math, mechanism, step by step) · 6. **Applications & use in practice** · 7. **Key figures** (embedded) · 8. **Code / hands-on** (runnable, minimal, commented) · 9. **Limitations, debates & open questions** · 10. **Annotated references** (seminal work first, each with why it matters + working link) · 11. **Further reading / learning path**.

Write at PhD-student level: rigorous and precise, but explain every non-obvious step; define jargon.

## Step 5 — Build the PDF

`mkdir -p` the run folder `<library-root>/<slug>/` first, then:

1. Write the full document as Markdown to a **temp file**, along with any figure PNGs it references by absolute path.
2. Convert to PDF with this command (`xelatex` comes from any LaTeX distribution — TinyTeX, MacTeX, or TeX Live):

   ```bash
   pandoc "<TMP>/doc.md" \
     -o "$HOME/find-out/<slug>/find-out_<slug>.pdf" \
     --pdf-engine=xelatex \
     --toc --toc-depth=3 \
     -V geometry:margin=1in \
     -V colorlinks=true -V linkcolor=blue -V urlcolor=blue \
     -V fontsize=11pt \
     --syntax-highlighting=tango
   ```
3. Confirm the `.pdf` exists and is non-empty (`ls -la`, `file`).
4. **Retry until it works** (up to 3 attempts), changing something each time: (1) read the LaTeX error and fix the offending Markdown (unbalanced `$`, a `$…$` closed right before a digit, a bad table/image path); (2) simplify — drop a broken figure, replace exotic Unicode with plain equivalents; (3) fall back to `--pdf-engine=pdflatex`, drop `--toc`, or `--syntax-highlighting=none`. Only after 3 genuine failures, save the Markdown as a fallback and tell the user exactly what blocked the PDF. Never silently produce nothing.

Keep the temp Markdown — Step 6 reuses its content for the audio script.

## Step 6 — Generate a NotebookLM-style audio overview (two-host podcast)

Produce a spoken "podcast": two hosts having a natural, engaging conversation that teaches the subject. Save it as an MP3 next to the PDF.

**Use NEURAL voices for natural, human-sounding audio** — the built-in macOS `say` voices sound robotic. Default engine: **`edge-tts`** (Microsoft's free neural voices — no API key, needs internet). Install if missing: `python3 -m pip install --user edge-tts`. Voices:

- **HOST_A → `en-US-AvaMultilingualNeural`** (female; expressive, friendly — the curious host)
- **HOST_B → `en-US-AndrewMultilingualNeural`** (male; warm, confident — the explainer)

**6a. Write the script** — ~18–34 turns of natural back-and-forth (~6–12 min): a hook, background, the core idea via a plain-language analogy, the deeper mechanics, the verdict, real-world uses, and a wrap-up. Rules for the spoken text: conversational (contractions, short sentences, real reactions, occasional names); **never read equations, code, URLs, or citation IDs aloud** — say them in words; spell out acronyms on first use; write numbers as words where it helps ("eight billion", not "8B"); no stage directions or labels — just the sentences to speak.

**6b. Synthesize** each turn with edge-tts, one MP3 per turn, alternating voices. Do it in a small async Python script and **run it in the background** — each neural turn is a ~5–7 s network call, so a full episode takes several minutes. Make the loop **resumable** (skip any `seg_NNN.mp3` already present and non-empty) and **retry each turn up to 3×** on network errors:
```python
import edge_tts, asyncio
await edge_tts.Communicate(text, "en-US-AvaMultilingualNeural", rate="+6%").save("seg_000.mp3")
```

**6c. Stitch** into an MP3 with a short gap between turns:
```bash
ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 0.30 -c:a libmp3lame -q:a 3 "$T/gap.mp3" -loglevel error
: > "$T/list.txt"
for f in "$T"/seg_*.mp3; do printf "file '%s'\nfile '%s'\n" "$f" "$T/gap.mp3" >> "$T/list.txt"; done
ffmpeg -y -f concat -safe 0 -i "$T/list.txt" -c:a libmp3lame -q:a 3 \
  "$HOME/find-out/<slug>/find-out_<slug>_podcast.mp3" -loglevel error
```

**6d. Verify / fallback** — confirm the MP3 exists with non-zero duration (`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <file>`). If `edge-tts` is unavailable (no internet), fall back to macOS `say` with two distinct voices (`say -v Samantha -r 180 -f turn.txt -o seg.aiff` / `say -v Daniel …`) so the user still gets audio — and tell them it's the lower-quality offline fallback. Never silently skip the audio.

Also save the transcript as `find-out_<slug>_script.txt` in the run folder.

## Step 7 — Report to the user

Give the exact paths of all deliverables (PDF, MP3, transcript), a 2–3 line summary of what's inside, the audio length, and anything notable (conflicting evidence, a must-read paper, a gap you couldn't fill).

## Quality bar

- **Exhaustive, not superficial.** Many sources, cross-checked; if you found only a handful, keep searching.
- **Every citation and figure link is real and verifiable.** No fabrication — if unsure, say so.
- **Self-contained.** A reader should understand the subject from the document alone.
- **Honest about uncertainty.** Distinguish established fact from preliminary/preprint findings from your own inference.
