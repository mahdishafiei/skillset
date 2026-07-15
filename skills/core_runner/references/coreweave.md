# CoreWeave (brineylab) — facts, endpoints, gotchas

Source: `github.com/brineylab/coreweave-docs` + lab announcements + hard-won experience.

## Clusters (separate regions, separate buckets)

| Cluster | GPUs | Per-GPU (VRAM / CPU / RAM / NVMe) | Bucket | For |
|---|---|---|---|---|
| **B200** (EU-SOUTH-04A) | 16×8 = 128 | 180 GB / 128 / ~2 TB / 28 TB | `brineylab-eu` (273 TiB) | Training + Inference |
| **RTX PRO 6000** (US-EAST-13A) | 12×8 = 96 | 96 GB / 128 / ~956 GB / 7 TB | `brineylab-us-east` (100 TiB) | Inference |

Connect: `ssh <user>@sunk.<cluster-id>.coreweave.app` (SSH keys synced via Active Directory).

## Storage

| Path | Scope | Size | Persistent |
|---|---|---|---|
| `/mnt/home/<user>` | per-user, shared (DFS) | 1 TB | yes — keep clean, no datasets/results |
| `/mnt/data/` | shared (DFS) | 4 TB | yes — archive to object storage + delete |
| `/tmp/` | local to node (NVMe) | 7 TB (RTX) / 28 TB (B200) | **NO — ephemeral**; job scratch, copy out at end |
| object storage | S3 via `s5cmd` | 273 / 100 TiB | yes |

## Object storage (s5cmd)

Keys: CoreWeave console → Administration → Object storage access keys → Create key. `s5cmd` reads
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

Endpoints (choose by where s5cmd runs):
- **compute/login nodes (inside CoreWeave):** `http://cwlota.com` (internal, fast)
- **Scripps servers (external):** `https://cwobject.com`

```
s5cmd --endpoint-url <EP> ls   s3://<bucket>/<user>/...
s5cmd --endpoint-url <EP> sync ./local/  s3://<bucket>/<user>/path/
s5cmd --endpoint-url <EP> cp   s3://.../file  ./local/
```

## Containers (required — no system Python/CUDA on nodes)

Pyxis via `#SBATCH --container-image=` + `--container-mounts=`. Images:
- `/mnt/data/containers/deeplearning_v<DATE>.sqsh` — lab image (torch, transformers, accelerate).
  **Confirm current filename:** `ls /mnt/data/containers/`.
- `nvcr.io/nvidia/pytorch:<tag>` — NVIDIA base (CUDA+torch only; pip-install the rest).

Mount: `--container-mounts=/mnt/home/${SLURM_JOB_USER}:/mnt/home/${SLURM_JOB_USER},/mnt/data:/mnt/data,/tmp:/tmp`
plus `--no-container-mount-home`.

## Partitions — the `all` partition is GONE (updated)

Four priority tiers. **Omit `-p` → you land in `hpc-mid` (the default; use this for standard work).**

| Partition | Priority | Behavior |
|---|---|---|
| `hpc-prod` | top | unpreemptible |
| `hpc-high` | high | preempts mid + low |
| **`hpc-mid`** | **default** | standard work (where you land with no `-p`) |
| `hpc-low` | lowest | preemptible, **auto-requeues** when GPUs free up (`JobRequeue=1`) |

- **Default to `hpc-mid`.** Use `hpc-low` only for backlogs of short jobs to soak idle GPUs
  (auto-requeue makes preemption safe): `sbatch -p hpc-low --gres=gpu:1 --time=20:00 job.sh`.
- The GPU-type partitions `b200` / `rtxp6000` still work (same priority as `hpc-mid`).
- **A script with `#SBATCH --partition=all` will NOT schedule** — change it to `hpc-mid`.
- Default per-GPU if unspecified: B200 16 CPU + ~242 GiB; RTX 12 CPU + ~89 GiB.

## Time limit — 24 h default cap (updated)

**B200 jobs have a default 24-hour limit.** If a job needs more, set `--time` explicitly
(`#SBATCH --time=D-HH:MM:SS`). Better for long work: shard into units that each finish well under
24 h and rely on resumability (re-`sbatch` to continue). Always set a realistic `--time` so hung
jobs die.

## Monitoring
`squeue -u $USER` · `df -h /mnt/data` · `df -h /tmp` · `scancel <jobid>` · logs in `/mnt/home/$USER/logs/`.

## Rules
- **Never run compute (or Claude) on the login node** — shared; heavy use locks everyone out.
- Keep `/mnt/home` + `/mnt/data` clean; scratch on `/tmp`; archive to object storage + delete local.
- **Coordinate large jobs** (many GPUs) in Slack `#coreweave-scripps-internal` before submitting.

## GOTCHAS (learned the hard way)

1. **CPU thread oversubscription = ~3× slowdown.** Multiple tasks share a 128-core node; each process
   defaults to ~128 intra-op threads → thrash. Cap per task: `OMP_NUM_THREADS`/`MKL_NUM_THREADS`/
   `OPENBLAS_NUM_THREADS`/`NUMEXPR_NUM_THREADS` ≈ `--cpus-per-task`, plus the framework equivalent
   (e.g. `torch.set_num_threads(...)`).
2. **Array design:** a **fixed-size array (= #concurrent slots) whose tasks each loop a strided slice
   of a manifest** beats one-array-task-per-unit — avoids SLURM `MaxArraySize` and re-staging.
3. **Resumability:** each unit skips if its output already exists in object storage → requeue,
   preemption, and hitting the 24 h cap are all free; just re-`sbatch`.
4. **Stage inputs to `/tmp` once per task** (not per unit); read compute inputs from local NVMe.
5. **Pull inputs/weights from source (HF/URL/DFS)** rather than hand-copying; for HF prefer public
   repos, weights-only, and stage a tokenizer so nodes can run offline (`HF_HUB_OFFLINE=1`).
6. **Runtime path rewrite:** if configs hold absolute paths, rewrite them on the node to the local
   `/tmp` staged paths before running.
7. **Batch/chunk size is usually a speed/memory knob, not a result knob** — verify output is
   invariant to it, then pick the memory-safe value (huge all-at-once batches fragment memory / OOM
   with no speed gain).
8. **fp differences across GPU archs** (e.g. L40S vs B200) are ~1e-4 per value and wash out in
   aggregates — not a bug.
