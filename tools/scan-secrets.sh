#!/usr/bin/env bash
# Read-only secret and local-environment fingerprint scan.
# Usage: bash tools/scan-secrets.sh [directory]
set -u

scan_root=${1:-.}
cd "$scan_root" || exit 2

patterns=(
  'BEGIN [A-Z ]*PRIVATE KEY'
  'ghp_[A-Za-z0-9]{30,}'
  'gho_[A-Za-z0-9]{30,}'
  'github_pat_[A-Za-z0-9_]{20,}'
  'sk-[A-Za-z0-9]{30,}'
  'rc-[0-9a-f]{40,}'
  'tskey-auth-[A-Za-z0-9-]{20,}'
  'Bearer[[:space:]]+[A-Za-z0-9._-]{20,}'
  '(password|passwd|api[_-]?key|access[_-]?token)[[:space:]]*[:=][[:space:]]*[^<[:space:]]{12,}'
)

hits=0
for pattern in "${patterns[@]}"; do
  result=$(rg -n -i --hidden \
    -g '!.git/**' -g '!tools/scan-secrets.sh' -g '!*.pyc' -g '!*.pyo' -g '!*.png' -g '!*.jpg' \
    -e "$pattern" . 2>/dev/null || true)
  if [[ -n "$result" ]]; then
    printf '=== [%s] ===\n%s\n' "$pattern" "$result"
    hits=$((hits + 1))
  fi
done

if (( hits == 0 )); then
  echo 'SCAN OK: no high-confidence secret patterns found'
  exit 0
fi
echo "SCAN FAIL: $hits pattern group(s) matched"
exit 1
