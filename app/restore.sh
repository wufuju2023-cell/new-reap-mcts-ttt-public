#!/usr/bin/env bash
# Restore hook for a deployment-specific artifact backend.
# This public snapshot does not embed credentials or a provider client.
set -euo pipefail

source_ref=${1:-${REAP_ARTIFACT_SOURCE:-}}
target_dir=${2:-${REAP_OUTPUT_DIR:-/workspace/out}}

if [[ -z "$source_ref" ]]; then
  echo "usage: $0 <artifact-source> [target-dir]" >&2
  echo "set REAP_ARTIFACT_SOURCE in the deployment environment" >&2
  exit 2
fi

mkdir -p "$target_dir"
echo "[restore] provider-specific restore is not bundled in this public snapshot"
echo "[restore] source=$source_ref target=$target_dir"
echo "[restore] implement the backend with runtime credentials and verify checksums before activation"
