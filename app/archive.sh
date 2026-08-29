#!/usr/bin/env bash
# Create a local, content-addressed runtime archive.
# Remote upload is intentionally left to the deployment environment.
set -euo pipefail

out_dir=${1:-${REAP_OUTPUT_DIR:-/workspace/out}}
timestamp=$(date -u +%FT%TZ)
archive="$out_dir/state-$timestamp.tar.zst"

[[ -d "$out_dir" ]] || { echo "[archive] output directory not found: $out_dir" >&2; exit 1; }
echo "[archive] writing $archive"
tar -I zstd -cf "$archive" -C "$out_dir" \
  checkpoints value_head.pt ttt_buffer.jsonl rttt_metrics.jsonl 2>/dev/null || true

{
  echo "# archive $timestamp"
  find "$out_dir" -maxdepth 2 -type f \
    ! -name 'state-*.tar.zst' -print0 2>/dev/null |
    xargs -0 -r sha256sum | sort
} > "$out_dir/hash.txt"
echo "[archive] hash manifest: $out_dir/hash.txt"
