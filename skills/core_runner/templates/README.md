# <JOBNAME> — CoreWeave bundle

## ▶ How to run (initiate the job)

> This bundle only *prepares* the job. Run it yourself on the cluster — never on the login node's
> shell beyond `sbatch`, and never run Claude on the cluster.

```bash
# 1. Stage inputs -> object storage  (machine with s5cmd + keys; Scripps or login node)
export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  CW_USER=<cluster-username>
bash stage_inputs.sh

# 2. Put this folder + keys on the login node
#    copy to /mnt/home/$USER/<JOBNAME>/  , then fill AWS keys in env/job.env
ls /mnt/data/containers/          # confirm the container .sqsh in slurm/run.sbatch

# 3. Submit (this is the trigger)
ssh <user>@sunk.<cluster-id>.coreweave.app
cd /mnt/home/$USER/<JOBNAME>
sbatch slurm/run.sbatch
squeue -u $USER                   # watch; logs in /mnt/home/$USER/logs/

# 4. Fetch results (back on Scripps)
bash fetch_results.sh
```

**Resumable:** if a job is preempted or hits the time cap, just re-run `sbatch slurm/run.sbatch` —
finished units are skipped.

---

## What this job does
<one-paragraph plain-English description of the science + what it computes>

## Job spec
- **Cluster / partition / time:** <B200|RTX> · hpc-mid · --time=<...>
- **Unit of work:** <what one array task/unit does> (<N> units)
- **Inputs:** <data / weights + where staged from>
- **Outputs:** <what lands in object storage results/>
- **Resources per task:** <gpus/cpus/mem>

## Files
- `scripts/` — compute script (+ manifest gen / input download if used)
- `configs/` — config (+ manifest.tsv)
- `env/job.env` — scratch/caches/thread-caps/keys/bucket
- `slurm/run.sbatch` — the job
- `stage_inputs.sh` / `fetch_results.sh` — object-storage transfer

## Notes / knobs
<container image, concurrency, shard size, any assay/method caveats, downstream step if any>
