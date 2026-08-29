"""v2/runner.py — V2 最小 harness（code-1）：元动作循环 + 塔 + Eff + 样本输出。
循环语义（spec 00）：π_θ 元动作（此处 mock）→ 类型检查/执行 → Eff/Tower 更新 → 记录样本。
样本格式与 v1_sink 兼容（kind: node_visited/task_done + tower/effect 事件字段）。
"""
import json
import random
import time
from dataclasses import dataclass
from typing import List, Optional

from .eff_registry import EffSpec, EffClass, lookup, public_verifiers
from .tower import Tower, TowerEntry, GateFn


@dataclass
class V2State:
    goal: str
    tower: Tower
    obs_history: List[dict] = None
    depth_budget: int = 64

    def __post_init__(self):
        if self.obs_history is None:
            self.obs_history = []


class V2Harness:
    def __init__(self, gate: Optional[GateFn] = None, seed: int = 42, sink_path: str = "/tmp/v2_rollout.jsonl"):
        self.gate = gate or (lambda e: True)
        self.rng = random.Random(seed)
        self.sink_path = sink_path
        self._steps = 0

    def _sink(self, kind: str, **kw) -> None:
        rec = {"kind": kind, "ts": time.strftime("%FT%TZ", time.gmtime()), "step": self._steps, **kw}
        with open(self.sink_path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def step(self, st: V2State, action_text: str) -> dict:
        """Mock 元动作 → 合法化/执行 → 更新（返回描述；真实内核验证交由外部 Lean）。"""
        self._steps += 1
        kind, _, rest = action_text.partition(":")
        obs = None
        if kind == "effect":
            verifier = rest.strip() or "arith-check"
            spec = EffSpec(name=verifier, in_vals=[self.rng.randint(0, 9) for _ in range(3)],
                           verifier=verifier, klass=EffClass.DETERMINISTIC)
            obs = lookup(spec)
            st.obs_history.append({"effect": verifier, "value": obs.value, "ok": obs.ok})
        elif kind == "adddecl":
            name, body = rest.split("~", 1) if "~" in rest else (rest.strip(), "rfl")
            deps = [x.get("verifier", "") for x in st.obs_history[-3:]]
            e = TowerEntry(name=name, body=body, deps=[d for d in deps if d])
            ok = self.gate(e)
            entered = st.tower.register(e, ok)
            if entered:
                self._sink("tower", name=name, depth=st.tower.depth(e), height=st.tower.height())
            else:
                self._sink("tower_reject", name=name)
            return {"entered": entered, "name": name}
        elif kind == "fillhole":
            return {"fillhole": rest}
        elif kind == "patch":
            return {"patch": rest}
        else:
            return {"unknown_action": action_text}
        self._sink("effect", verifier=spec.name, value=obs.value, ok=obs.ok)
        return {"effect": spec.name, "obs": obs.value, "ok": obs.ok}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--sink", default="/tmp/v2_rollout.jsonl")
    p.add_argument("--gate", choices=["always", "half"], default="always")
    args = p.parse_args()

    gate = (lambda e: True) if args.gate == "always" else (lambda e: self_rng.random() < 0.5)
    h = V2Harness(gate=gate, sink_path=args.sink)
    st = V2State(goal="1³+…+n³=(n(n+1)/2)²", tower=Tower())
    acts = ["effect:arith-check", "effect:sqsum-check", "adddecl:lemma_step~by omega", "patch:∀→∃",
            "fillhole:h0", "adddecl:lemma_fin~by simp", "effect:arith-check", "adddecl:broken~by sorry_unsafe"]
    for i, a in enumerate(acts[: args.steps]):
        print(f"{i:02d} {a:34s} -> {h.step(st, a)}", flush=True)
    print(f"steps={args.steps} | tower size={len(st.tower.lib)} | height={st.tower.height()}\n" + "\n".join(
        f"  {e.name} (deps={e.deps})" for e in st.tower.lib))


if __name__ == "__main__":
    main()
