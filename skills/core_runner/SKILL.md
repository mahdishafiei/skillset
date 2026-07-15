---
name: core_runner
description: >
  Package any locally-developed compute job into a self-contained, resumable bundle ready to run on
  the brineylab CoreWeave clusters (B200 EU / RTX PRO 6000 US) via SLURM. Task-agnostic — works for
  ML training/inference, simulations, bioinformatics pipelines, batch processing, anything that runs
  as a command in a container. Handles the cluster conventions: container image + mounts, /tmp
  scratch + cache redirects, s5cmd object-storage staging in/out, CPU thread caps, SLURM partitions
  + the 24h time cap, and resumability. Invoke it and describe the job in plain English — with any
  links, file/folder paths, .md design docs, a draft script, and a target output folder; it reads
  those materials, extracts the spec, and generates the compute scripts + sbatch + staging tailored
  for CoreWeave. Use whenever the user wants to prepare / port / "make ready" a job for CoreWeave /
  the B200 / the RTX cluster / SLURM / sbatch. Claude builds the scripts locally; the user runs them
  on the cluster (never run Claude or compute on the login node).
---

# core_runner — package a job for the CoreWeave SLURM cluster

Turn a command the user has built + validated **locally** into a folder they copy to CoreWeave and
`sbatch`. The compute logic is theirs; this skill wraps it in the lab's cluster conventions so it
runs in a container, stages data via object storage, uses the right partition/time, and (for
parallel or long jobs) is resumable.

**Read `references/coreweave.md` first** — cluster/storage/container/partition/time facts, the
object-storage endpoints, and the non-obvious gotchas. Don't reinvent them.

## How you're invoked (intake — do this before writing anything)

The user activates this skill and **describes the job in plain English**. They will usually also
give you materials and a destination:
- **links** (papers, GitHub repos, docs) → fetch and read them,
- **local paths / files / folders** (a draft script, configs, sample data, a design `.md`) → open and
  read them with the file tools,
- **a target output folder** (where the bundle should go) and often a **source folder** holding
  their draft code/inputs.

**Ingest everything they pointed at first** — read every provided file/path and fetch every link, and
skim any existing code in the source folder (reuse it as the compute script rather than rewriting).
Build a mental model of: what the job computes, what it reads/writes, and how it splits into units.

## Scope first, build second — talk it through, agree, THEN generate

Treat this as a short collaboration, not a one-shot generator. **Do NOT create any files until you and
the user have agreed on the plan.** Work in **short, precise, step-by-step turns** — state the current
step and the single next action, not long essays.

1. **Rationalize the project (science + mapping).** After ingesting the materials, write a *short*
   summary of your understanding: the **science goal** (what's being computed and why) and how it maps
   to a cluster job (job shape, what one **unit** is, inputs + where they come from, outputs,
   resources, cluster). Reason about the science, not just mechanics — is this the right
   decomposition? does the output/metric make sense? any correctness pitfalls or better approaches?
2. **Ask what's missing (important).** Explicitly list the open questions and anything you need but
   can't infer — the exact compute command, the unit definition, per-task resources + walltime, the
   cluster, the container, where weights/data live, the output folder. **Ask; don't assume the
   important ones.** Prefer a tight list of concrete questions.
3. **Iterate.** Go a few rounds of science + scoping back-and-forth until the terms are settled.
4. **Confirm, then build.** Once you've agreed, say in one line what you're about to generate, then
   create the bundle (Steps 1–4) **into the folder the user named** (fall back to
   `<jobname>_coreweave/` only if none given).

After building, hand back a **short numbered "next steps" list** (stage → copy → `sbatch` → fetch) —
the exact commands, nothing more.

## Step 0 — the spec to nail down (fill from their materials, ask for the rest)

1. **Compute command** — the exact command that does the work inside the container.
2. **Job shape:**
   - **Single** — one node/command → use `templates/single.sbatch`.
   - **Parallel / many independent units** → use `templates/array.sbatch`: a **manifest** (one line
     per unit) + a **fixed-size array (≈ #GPUs or #concurrent slots) whose tasks each loop their
     strided slice** of the manifest. (Prefer this over one-array-task-per-unit: avoids SLURM
     MaxArraySize and re-staging per unit.)
3. **Inputs / outputs** — what the job reads and writes. Big inputs → object storage, pulled to
   `/tmp` at job start. If inputs are on public HuggingFace/other URLs, download on the login node
   or job start rather than hand-copying (see the optional `download_inputs` pattern in the ref).
4. **Resources** — GPUs/CPUs/mem per task, and **`--time`** (see time cap below).
5. **Target cluster** — B200 (`brineylab-eu`) or RTX PRO 6000 (`brineylab-us-east`).
6. **Output folder** — default `<jobname>_coreweave/` next to the source.

## Step 1 — create the package (self-contained)
```
<jobname>_coreweave/
├── scripts/            # the compute script + helpers: gen_manifest.py, download_inputs.py, (report)
├── configs/            # config + generated manifest.tsv (array jobs)
├── inputs/  (or data/) # small inputs, or produced by download_inputs.py / a staging step
├── env/job.env         # from templates/job.env — scratch/caches/thread-caps/keys/bucket
├── slurm/run.sbatch    # from templates/{single,array}.sbatch
├── stage_inputs.sh     # from templates/stage_inputs.sh   (Scripps -> object storage)
├── fetch_results.sh    # from templates/fetch_results.sh  (object storage -> Scripps)
└── README.md           # exact run steps (+ HANDOFF.md if another chat will drive it)
```

### Checklist — consider each; use only what the job needs (most jobs skip several)
This is a menu, **not** a mandatory list. Only a few items are always needed; the rest are
conditional — decide per job and skip what doesn't apply.

**Always (every job):**
- **Compute script** copied in, arg-driven (reads inputs, writes outputs).
- **`env/job.env`** — bucket set for the cluster; thread caps kept; AWS keys left blank.
- **sbatch** — `hpc-mid`; explicit `--time`; container confirmed (`ls /mnt/data/containers/`);
  mounts; stage-in to `/tmp`; stage-out; `/tmp` cleanup.
- **stage_inputs.sh / fetch_results.sh** — bucket + endpoints set.
- **Local validation** — run one unit against a temp on-node layout before shipping.
- **README** — the run steps.

**Only if it applies (skip otherwise):**
- **Array + manifest** (`gen_manifest.py`) — only if there are many independent units; a single job
  uses `single.sbatch` and no manifest.
- **Resumable skip** — for array / long / preemptible jobs; a short single job may not need it.
- **`download_inputs.py`** — only if inputs/weights come from HF/URLs; if inputs are already local,
  just stage them (no downloader).
- **Runtime path rewrite** — only if a config holds absolute paths that must point at `/tmp`.
- **Offline env + tokenizer staging** — only for jobs that would otherwise hit the network (e.g. ML);
  otherwise drop `HF_HUB_OFFLINE` from `job.env`.
- **HANDOFF.md** — only if another chat/person will run it.
- **Downstream post-processing** (e.g. a `make_report.py`) — only if the job needs local analysis
  after `fetch_results.sh`.

## Step 2 — fill the templates (`templates/` in this skill dir)
- **`job.env`**: set `BUCKET` for the target cluster; keep the `/tmp` scratch + cache redirects; keep
  the **CPU thread caps** (critical — see gotchas); leave AWS keys blank for the user.
- **`run.sbatch`** (single or array): set `--job-name`; `--partition` (**default `hpc-mid`**);
  **always set `--time` explicitly** (B200 caps jobs at 24 h by default — see below); resources; the
  `--container-image` (`ls /mnt/data/containers/` to confirm current `.sqsh`); the container mounts;
  the stage-in, the compute command, and the stage-out. For arrays: the per-unit **resumable skip**
  (s5cmd-`ls` the expected output → continue if it exists).
- **`stage_inputs.sh` / `fetch_results.sh`**: set the same `BUCKET`; external endpoint
  `cwobject.com` from Scripps, internal `cwlota.com` from compute nodes.

## Step 3 — make it robust
- **Resumable / idempotent** (arrays + long jobs): each unit checks whether its result already
  exists in object storage and skips. Then requeue/preemption/hitting the time cap are all safe —
  just re-`sbatch`.
- **Thread caps**: set `OMP_NUM_THREADS`/`MKL`/`OPENBLAS`/`NUMEXPR` ≈ `--cpus-per-task` in `job.env`
  and the framework equivalent in the script (e.g. `torch.set_num_threads(...)`). Without this,
  multiple tasks/node oversubscribe the 128 cores (~3× slowdown). Non-negotiable.
- **Time**: the B200 default cap is **24 h**. Set `--time` explicitly; if a job needs >24 h either
  request it or (better) shard so each task finishes well under the cap and rely on resumability.

## Step 4 — validate locally, then document
- Simulate the on-node layout (stage a couple inputs to a temp dir, rewrite any absolute paths to
  local `/tmp` paths, run ONE unit) and confirm correct output — **fully offline** if the job would
  otherwise hit the network (`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`, etc.). Diff against a known
  result if you have one.
- Write `README.md` from `templates/README.md` — it **must lead with a prominent "How to run
  (initiate the job)" block** (stage → copy → `sbatch` → fetch, exact commands) as the very first
  section, before any explanation. If a separate chat/person will run it, also write a self-contained
  `HANDOFF.md` that likewise opens with that run block, then context + inlined scripts + gotchas.

## Run flow the package supports (user runs this on the cluster)
```
# machine with internet + s5cmd (login node ok):
python scripts/download_inputs.py     # if pulling inputs from HF/URLs (optional)
bash stage_inputs.sh                  # inputs -> object storage
# copy the folder to /mnt/home/$USER/<jobname>, fill AWS keys in env/job.env
sbatch slurm/run.sbatch               # resumable; re-submit to resume
bash fetch_results.sh                 # results <- object storage
```

## Guardrails (lab rules)
- **Never run Claude/compute on the login node.** Build + test locally; move scripts over.
- **Coordinate large jobs** (many GPUs) in Slack `#coreweave-scripps-internal` first.
- Keep `/mnt/home` (1 TB) + `/mnt/data` (4 TB) clean; scratch on `/tmp`; archive results to object
  storage and delete local copies.
- Always run in a container; always set a realistic `--time`.
