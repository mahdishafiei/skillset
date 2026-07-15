#!/bin/bash
# fetch_results.sh — pull results from CoreWeave object storage. Run on a Scripps machine.
#   export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  CW_USER=<cluster-username>
#   bash fetch_results.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${AWS_ACCESS_KEY_ID:?}"; : "${AWS_SECRET_ACCESS_KEY:?}"; : "${CW_USER:?set CW_USER}"
JOBNAME="<JOBNAME>"
BUCKET="brineylab-eu"                 # brineylab-us-east for the RTX cluster
EP="https://cwobject.com"
S3="s3://${BUCKET}/${CW_USER}/${JOBNAME}"
mkdir -p "$HERE/results"
s5cmd --endpoint-url "$EP" sync "$S3/results/*" "$HERE/results/"
echo "downloaded -> $HERE/results/  ($(find "$HERE/results" -type f | wc -l) files)"
