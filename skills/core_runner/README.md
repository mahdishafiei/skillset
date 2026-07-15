# core_runner

> Build a job locally → get a **self-contained, resumable SLURM bundle** ready to `sbatch` on the brineylab **CoreWeave** clusters (B200 / RTX PRO 6000).

`/core_runner` (or "make this ready for the B200 / coreweave / the cluster") takes a compute
command you've built and validated **locally** and wraps it in the lab's cluster conventions so it
just runs. Task-agnostic — ML training/inference, simulations, bioinformatics pipelines, batch
processing: anything that runs as a command in a container.

Claude builds the scripts; **you run them on the cluster** (never run Claude or compute on the login
node).

## What it produces

A `<jobname>_coreweave/` folder:

- **`env/job.env`** — per-task scratch on local NVMe (`/tmp`), all caches redirected there, **CPU
  thread caps** (so tasks don't oversubscribe the 128-core node → ~3× slowdown), object-storage
  creds + bucket/endpoints.
- **`slurm/run.sbatch`** — a **single** or **array** job, in a container with the right
  `--container-mounts`, on **`hpc-mid`** (the default tier), with **`--time` set explicitly** (B200
  caps jobs at 24 h). Array jobs use a fixed-size array whose tasks each **loop a strided slice of a
  manifest** and are **resumable** (skip units whose output already exists in object storage).
- **`stage_inputs.sh` / `fetch_results.sh`** — `s5cmd` push/pull to the cluster bucket
  (`cwobject.com` from Scripps, `cwlota.com` from compute nodes).
- **`README.md`** (+ optional `HANDOFF.md`) with the exact run steps.

Before shipping, it **validates one unit locally** (offline where possible) to confirm the packaged
command actually runs.

## Usage

```
/core_runner        # then point it at your script + inputs, and say B200 or RTX
```

Then on the cluster:

```bash
bash stage_inputs.sh                 # inputs -> object storage
# copy the folder to /mnt/home/$USER/<jobname>, fill AWS keys in env/job.env
sbatch slurm/run.sbatch              # resumable; re-submit to resume
bash fetch_results.sh                # results <- object storage
```

## What it knows (so you don't have to)

- **Clusters:** B200 (EU, `brineylab-eu`, 128 GPUs) vs RTX PRO 6000 (US, `brineylab-us-east`, 96).
- **Storage:** `/mnt/home` (1 TB, keep clean), `/mnt/data` (4 TB), `/tmp` (ephemeral NVMe scratch),
  object storage via `s5cmd`.
- **Containers:** required; lab image `/mnt/data/containers/deeplearning_v*.sqsh` or NGC PyTorch.
- **Partitions:** `all` is gone; default **`hpc-mid`**; `hpc-low` (auto-requeue) for short soak jobs;
  `hpc-prod`/`hpc-high` for priority; `b200`/`rtxp6000` still valid.
- **Time:** 24 h default cap on B200 — always set `--time`.
- **Gotchas:** thread oversubscription, resumable array design, stage-to-`/tmp`-once, pull weights
  from HF, runtime path rewrites, batch-size-is-a-speed-knob, cross-arch fp differences.

See [`references/coreweave.md`](references/coreweave.md) for the full facts + gotchas, and
[`templates/`](templates) for the fill-in `job.env`, `single.sbatch`, `array.sbatch`, and the
staging scripts.

## Requirements

- On the machine that stages/fetches: **`s5cmd`** + CoreWeave object-storage access keys.
- Cluster access (SSH via Active Directory) to submit.
