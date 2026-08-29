"""v2/gate_lean.py — 真实 checkProof 门（reap-lean 容器执行 Lean 验证）。
引理条目: entry.type（目标语句）+ entry.body（证明策略）。
gate 语义: 容器内 lean 编译 `theorem <name> : <type> := by <body>`，编译通过且无 unresolved goals
即视为 kernel-valid（标准库命题，无需 mathlib）。
"""
import os
import subprocess
import tempfile

from .tower import TowerEntry

LEAN_IMAGE = os.environ.get("V2_LEAN_IMAGE", "reap-lean:local")
GATE_TIMEOUT = 120
PKG_ROOT = os.path.dirname(os.path.abspath(__file__))


def gate_lean(entry: TowerEntry, image: str = LEAN_IMAGE) -> tuple[bool, str]:
    src = f"""theorem {entry.name} : {entry.type} := by
  {entry.body}

#eval IO.println "%%GATE_OK%%"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            ["podman", "run", "--rm", "-v", f"{path}:/ws/gate.lean:ro", image,
             "lean", "/ws/gate.lean"],
            capture_output=True, text=True, timeout=GATE_TIMEOUT)
        out = r.stdout + r.stderr
        low = out.lower()
        ok = ("error" not in low) and ("unsolved" not in low)
        return ok, out[-400:]
    finally:
        os.unlink(path)
