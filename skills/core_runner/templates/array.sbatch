#!/bin/bash
# array.sbatch — parallel CoreWeave job. A fixed-size array; each task loops its strided slice of
# configs/manifest.tsv and is RESUMABLE (skips units whose output already exists in object storage).
# Fill: <JOBNAME>, <NTASKS>, resources, <CONTAINER>, the manifest columns, the COMPUTE COMMAND, and
# the output naming. Submit:  sbatch slurm/run.sbatch
#
#SBATCH --job-name=<JOBNAME>
#SBATCH --partition=hpc-mid              # default tier; hpc-low for short soak jobs (auto-requeue)
#SBATCH --array=0-<NTASKS_MINUS_1>%<NTASKS>   # e.g. 0-127%128 (one task per concurrent GPU slot)
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16               # job.env caps threads to this
#SBATCH --mem=64G
#SBATCH --time=24:00:00                  # ALWAYS set (B200 default cap is 24h). Keep each task < cap;
                                         # if a task is killed, re-sbatch resumes (idempotent).
#SBATCH --requeue
#SBATCH --output=/mnt/home/%u/logs/%x_%A_%a.out
#SBATCH --error=/mnt/home/%u/logs/%x_%A_%a.err
#SBATCH --container-image=/mnt/data/containers/deeplearning_v2026-05-26.sqsh   # `ls /mnt/data/containers/`
#SBATCH --container-mounts=/mnt/home/${SLURM_JOB_USER}:/mnt/home/${SLURM_JOB_USER},/mnt/data:/mnt/data,/tmp:/tmp
#SBATCH --no-container-mount-home

set -euo pipefail
REPO="/mnt/home/${SLURM_JOB_USER}/<JOBNAME>"
source "${REPO}/env/job.env"                      # -> JOB_WORK_DIR, caches, threads, keys, $S3, endpoints
EP="${S5_ENDPOINT_INTERNAL}"
NT="${SLURM_ARRAY_TASK_COUNT:-<NTASKS>}"; TASK="${SLURM_ARRAY_TASK_ID:-0}"
cd "${JOB_WORK_DIR}"; mkdir -p inputs out
echo "=== ${SLURM_JOB_NAME} task ${TASK}/${NT} on $(hostname) $(date) ==="

# ---- stage inputs + code + manifest to local NVMe ONCE ----
s5cmd --endpoint-url "$EP" sync "$S3/inputs/*"          inputs/
s5cmd --endpoint-url "$EP" cp   "$S3/configs/manifest.tsv" manifest.tsv
# (stage scripts/config too, or reference them from ${REPO})

# ---- this task's strided slice of the manifest (skip header) ----
mapfile -t UNITS < <(tail -n +2 manifest.tsv | awk -v t="$TASK" -v n="$NT" 'NR % n == t')
echo "task ${TASK}: ${#UNITS[@]} units"

for line in "${UNITS[@]}"; do
    # FILL: parse your manifest columns
    read -r idx arg1 arg2 <<<"$line"
    name="result_${arg1}_${arg2}.csv"          # FILL: output name for this unit
    dst="$S3/results/${name}"
    # resumable: skip if already done
    if s5cmd --endpoint-url "$EP" ls "$dst" >/dev/null 2>&1; then echo "SKIP $name"; continue; fi

    # FILL: your compute command for one unit (read inputs/, write out/${name})
    python3 "${REPO}/scripts/<YOUR_SCRIPT>.py" --in inputs --arg1 "$arg1" --arg2 "$arg2" --out "out/${name}"

    s5cmd --endpoint-url "$EP" cp "out/${name}" "$dst"; rm -f "out/${name}"
done
cd /tmp && rm -rf "${JOB_WORK_DIR}"
echo "=== task ${TASK} done $(date) ==="
