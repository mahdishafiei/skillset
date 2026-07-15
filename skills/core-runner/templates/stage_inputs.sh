#!/bin/bash
# stage_inputs.sh — push job inputs to CoreWeave object storage. Run on a machine with s5cmd + keys
# (Scripps node, or the cluster login node). Fill JOBNAME + what to sync.
#   export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  CW_USER=<cluster-username>
#   bash stage_inputs.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${AWS_ACCESS_KEY_ID:?}"; : "${AWS_SECRET_ACCESS_KEY:?}"; : "${CW_USER:?set CW_USER}"
JOBNAME="<JOBNAME>"
BUCKET="brineylab-eu"                 # brineylab-us-east for the RTX cluster
EP="https://cwobject.com"            # external endpoint (Scripps -> CoreWeave); cwlota.com if on-cluster
S3="s3://${BUCKET}/${CW_USER}/${JOBNAME}"

# if pulling inputs/weights from HF/URLs, fetch them first (populates ./inputs):
if [ ! -d "$HERE/inputs" ] || [ -z "$(ls -A "$HERE/inputs" 2>/dev/null)" ]; then
  [ -f "$HERE/scripts/download_inputs.py" ] && python3 "$HERE/scripts/download_inputs.py" --out "$HERE/inputs"
fi
# --exclude drops HF's local .cache metadata dirs
s5cmd --endpoint-url "$EP" sync --exclude "*/.cache/*" --exclude ".cache/*" "$HERE/inputs/" "$S3/inputs/"
s5cmd --endpoint-url "$EP" cp   "$HERE/configs/manifest.tsv" "$S3/configs/manifest.tsv"   # array jobs
echo "staged -> $S3   (verify: s5cmd --endpoint-url $EP ls $S3/)"
