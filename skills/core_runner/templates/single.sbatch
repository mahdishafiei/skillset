#!/bin/bash
# single.sbatch — one-node CoreWeave job. Fill: <JOBNAME>, resources, <CONTAINER>, the COMPUTE
# COMMAND, and the stage-in/out lists. Submit from the cluster login node:  sbatch slurm/run.sbatch
#
#SBATCH --job-name=<JOBNAME>
#SBATCH --partition=hpc-mid              # default tier; hpc-low for short soak jobs (auto-requeue)
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1                     # adjust
#SBATCH --cpus-per-task=16               # adjust; job.env caps threads to this
#SBATCH --mem=64G                        # adjust
#SBATCH --time=24:00:00                  # ALWAYS set (B200 default cap is 24h; raise if needed)
#SBATCH --output=/mnt/home/%u/logs/%x_%j.out
#SBATCH --error=/mnt/home/%u/logs/%x_%j.err
#SBATCH --container-image=/mnt/data/containers/deeplearning_v2026-05-26.sqsh   # `ls /mnt/data/containers/`
#SBATCH --container-mounts=/mnt/home/${SLURM_JOB_USER}:/mnt/home/${SLURM_JOB_USER},/mnt/data:/mnt/data,/tmp:/tmp
#SBATCH --no-container-mount-home
# #SBATCH --mail-type=ALL
# #SBATCH --mail-user='slack:USER-ID'

set -euo pipefail
REPO="/mnt/home/${SLURM_JOB_USER}/<JOBNAME>"      # where this bundle is checked out on the cluster
source "${REPO}/env/job.env"                      # -> JOB_WORK_DIR, caches, threads, keys, $S3, endpoints
EP="${S5_ENDPOINT_INTERNAL}"
cd "${JOB_WORK_DIR}"
echo "=== ${SLURM_JOB_NAME} on $(hostname) $(date) ==="; nvidia-smi -L || true

# ---- stage inputs to local NVMe ----
mkdir -p inputs out
s5cmd --endpoint-url "$EP" sync "$S3/inputs/*" inputs/     # adjust to your inputs

# ---- run (FILL your compute command; read from inputs/, write to out/) ----
python3 "${REPO}/scripts/<YOUR_SCRIPT>.py" --in inputs --out out

# ---- push results, clean scratch ----
s5cmd --endpoint-url "$EP" sync out/ "$S3/results/"
cd /tmp && rm -rf "${JOB_WORK_DIR}"
echo "=== done $(date) ==="
