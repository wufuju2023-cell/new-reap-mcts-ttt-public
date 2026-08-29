#!/bin/bash
# smoke.sh — 续接前一致性校验
set -euo pipefail
export PATH=/opt/venv/bin:$PATH
echo "[smoke] python: $(python3 --version 2>&1)"
python3 - <<'PY'
import torch, os
assert torch.cuda.device_count() >= 1, "no GPU"
print("[smoke] torch", torch.__version__, torch.version.hip, "gpus", torch.cuda.device_count())
PY
[ -f /workspace/out/value_head.pt ] && echo "[smoke] value_head.pt OK" || echo "[smoke] WARN value_head.pt missing"
[ -f /workspace/out/hash.txt ] && echo "[smoke] hash.txt OK ($(wc -l < /workspace/out/hash.txt) entries)" || echo "[smoke] WARN hash.txt missing"
echo "[smoke] PASS"
