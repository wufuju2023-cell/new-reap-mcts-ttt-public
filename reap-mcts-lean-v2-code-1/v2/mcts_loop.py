"""v2/mcts_loop.py — V2 MCTS 主循环（元动作空间; 复用 V1 容器执行模型）。
扩展: policy 采样(HTTP) → 动作执行(eff/tower/gate) → PUCT 选择/回溯 → 塔单调增长。
PUCT: c(t)=c_init+log((N+c_base+1)/c_base), U=c·p·√N/(1+n)。
"""
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional

from .eff_registry import EffSpec, EffClass, lookup
from .tower import Tower, TowerEntry
from .gate_lean import gate_lean
from .policy_client import PolicyClient
from .mine import detect

C_BASE, C_INIT = 3200.0, 1.0


@dataclass
class Node:
    state: str
    prior: float = 1.0
    n_visits: int = 0
    value_sum: float = 0.0
    children: dict = field(default_factory=dict)      # action_text -> Node


def c_init_for(N: float) -> float:
    return C_INIT + math.log((N + C_BASE + 1.0) / C_BASE)


class V2MCTS:
    def __init__(self, goal: str, policy: PolicyClient, tower: Tower, gate_mode: str = "lean",
                 num_samples: int = 4, seed: int = 42, series: list | None = None):
        self.goal = goal
        self.policy = policy
        self.tower = tower
        self.gate_mode = gate_mode           # "lean" = gate_lean; "mock" = always True
        self.ns = num_samples
        self.rng = __import__("random").Random(seed)
        self.root = Node(state=goal)
        self.log = []
        # 实验观测序列（H_obs）默认内置：立方和 1^3+...+n^3 前 10 项（多项式安全类原料）
        self.series = series or [0, 1, 9, 36, 100, 225, 441, 784, 1296, 2025]

    def _select(self, node: Node) -> str:
        N = float(node.n_visits)
        c = c_init_for(N)
        best, best_score = None, -1e9
        for a, child in node.children.items():
            Q = child.value_sum / max(child.n_visits, 1)
            U = c * max(child.prior, 1e-6) * math.sqrt(N) / (child.n_visits + 1.0)
            s = Q + U
            if s > best_score:
                best, best_score = a, s
        return best

    def _evaluate(self, action_text: str) -> tuple[float, str]:
        kind, _, rest = action_text.partition(":")
        if kind == "effect":
            verifier = rest.strip() or "arith-check"
            spec = EffSpec(action_text, [self.rng.randint(0, 9) for _ in range(3)], verifier)
            obs = lookup(spec)
            return (0.1 if obs.ok else -0.2), f"eff:{verifier} ok={obs.ok}"
        if kind == "adddecl":
            parts = rest.split("~", 1)
            typ = parts[0].strip() or "1 + 1 = 2"
            body = parts[1].strip() if len(parts) > 1 and parts[1] else "decide"
            e = TowerEntry(name=f"lem{len(self.tower.lib)+1}", type=typ, body=body)
            if self.gate_mode == "lean":
                ok, _l = gate_lean(e)
            else:
                ok = True
            entered = self.tower.register(e, ok)
            return (0.5 if entered else -0.3), f"adddecl:{typ[:20]} gate={ok}"
        if kind == "mine":
            cand = detect(self.series)
            if cand.cls == "F_k":
                e = TowerEntry(name=f"lem{len(self.tower.lib)+1}", body="decide",
                               deps=[], type=cand.stmt)
                ok, _l = gate_lean(e) if self.gate_mode == "lean" else (True, "mock")
                entered = self.tower.register(e, ok)
                return (0.5 if entered else -0.2), f"mine:{cand.kind} F_k score={cand.score}"
            return 0.05, f"mine:open F_c score={cand.score} (no gate)"
        if kind == "patch":
            return 0.0, f"patch:{rest[:20]}"
        if kind == "fillhole":
            return 0.0, f"fillhole:{rest[:20]}"
        return -0.5, "unknown"

    def run(self, steps: int = 16) -> dict:
        for _ in range(steps):
            node = self.root
            depth = 0
            while node.children and depth < 4:
                a = self._select(node)
                node = node.children[a]
                depth += 1
            prompt = f"Goal: {self.goal}\nlibrary: {[e.name for e in self.tower.lib]}\nAction:"
            samples = self.policy.sample(prompt, n=self.ns)
            for action_text, logp in samples:
                prior = math.exp(logp)
                if action_text not in node.children:
                    node.children[action_text] = Node(state=node.state + " | " + action_text,
                                                      prior=prior)
                r, note = self._evaluate(action_text)
                child = node.children[action_text]
                child.n_visits += 1
                child.value_sum += r
                node.n_visits += 1
                node.value_sum += r
                self.log.append({"depth": depth, "action": action_text, "r": round(r, 3),
                                 "tower": len(self.tower.lib), "h": self.tower.height(),
                                 "note": note, "ts": time.strftime("%FT%TZ", time.gmtime())})
        return {"steps": steps, "tower_size": len(self.tower.lib),
                "tower_height": self.tower.height(), "nodes": len(self.root.children),
                "log": self.log}
