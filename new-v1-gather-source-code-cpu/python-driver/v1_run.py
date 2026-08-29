#!/usr/bin/env python3
"""v1_run.py — BatchSolver 编排器（V1 spec 03）
每道题: 生成临时 Lean 文件（imports + example + reapMCTS + 成功标记）→ 容器内 `lake env lean` 执行
      → 解析 exit/输出 → sink 写入; checkpoint: state/<batch>/<id>.done
用法:
  v1_run.py --batch batch.jsonl --out out/b1 [--image ghcr.io/example-org/reap-lean:4.28.0-rc1-reap]
            [--policy http://127.0.0.1:8760] [--workers 1] [--continue]
"""
import argparse, json, os, subprocess, sys, tempfile, time
from pathlib import Path

def load_batch(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def make_lean(task, policy, value, ps, import_extra=""):
    imports = "\n".join(f"import {m}" for m in task.get("imports", []))
    opts = ""
    if policy:
        opts = (f'set_option reap.policy_endpoint "{policy}"\n'
                f'set_option reap.value_endpoint "{value}"\n'
                f'set_option reap.ps_endpoint "{ps}"\n')
    theorems = []
    for t in task.get("theorems", []):
        stmt = t["statement"]
        theorems.append(f"""theorem {t['name']} : {stmt} := by
  reapMCTS
""")
    return f"""import Reap
import Reap.Tactic.Syntax
{imports}
{import_extra}

{opts}
{chr(10).join(theorems)}
#eval IO.println "%%TASK_{task['id']}_DONE%%"
"""

def run_one(task, args, image):
    lean_src = make_lean(task, args.policy, args.value, args.policy)
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
        f.write(lean_src)
        lean_path = f.name
    host_out = Path(args.out) / f"{task['id']}.lean"
    host_out.write_text(lean_src)
    todo = f"cd /workspace/reap && lake env lean /batch/{task['id']}.lean"
    err = None
    try:
        r = subprocess.run(
            ["podman", "run", "--rm", "--network", "host",
             "-v", f"{host_out.parent}:/batch:ro", image,
             "bash", "-lc", f"cp /batch/{task['id']}.lean /workspace/reap/ && {todo} 2>&1 | tail -20"],
            capture_output=True, text=True, timeout=args.per_task_timeout)
        out = r.stdout + "\n" + r.stderr
        done = f"%%TASK_{task['id']}_DONE%%" in out
        err = "error" in out.lower() or not done
    except subprocess.TimeoutExpired:
        err = True
        out = "TIMEOUT"
    os.unlink(lean_path)
    return {"id": task["id"], "ok": not err, "out": out[-2000:]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--out", default="out/b1")
    ap.add_argument("--image", default="ghcr.io/example-org/reap-lean:4.28.0-rc1-reap")
    ap.add_argument("--policy", default="http://127.0.0.1:8760")
    ap.add_argument("--value", default="http://127.0.0.1:8760/value")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--per-task-timeout", type=int, default=300)
    ap.add_argument("--continue", dest="cont", action="store_true")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    state = out / "state"; state.mkdir(exist_ok=True)
    solved = failed = 0
    for task in load_batch(args.batch):
        done = state / f"{task['id']}.done"
        if args.cont and done.exists():
            print(f"[skip] {task['id']} (done)")
            continue
        print(f"[run ] {task['id']}", flush=True)
        res = run_one(task, args, args.image)
        (out / f"{task['id']}.log").write_text(res["out"])
        if res["ok"]:
            solved += 1
        else:
            failed += 1
        touched = done.touch()
        print(f"      -> {'SOLVED' if res['ok'] else 'FAILED'} ({res['out'][-80:].strip()[-60:]})", flush=True)
    print(f"summary: solved={solved} failed={failed}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
