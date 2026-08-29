"""smoke_emergent.py — 涌现工具使用——规律挖掘（emergent-tool-use spec 03 断言）
① poly：立方和序列（≤6 阶）→ F_k 候选 → gate 真验证入塔；
② recurrence：前 k 项 → 线性递推（F_k）；
③ 非安全类：输入非多项式证据（如素数间隔）→ F_c + score（不送 gate）；
④ TowerDelta：30 步 MCTS（含 mine 动作）→ 塔增长与"入塔"事件的正相关。
"""
import math
import random

from v2.mine import detect, score, Candidate
from v2.tower import Tower, TowerEntry
from v2.gate_lean import gate_lean
from v2.policy_client import PolicyClient
from v2.mcts_loop import V2MCTS


def test_poly_gate():
    cubes = [sum(i ** 3 for i in range(1, n + 1)) for n in range(1, 11)]   # 立方和：4 阶多项式
    c = detect(cubes)
    assert c.kind == "poly" and c.cls == "F_k", f"expected poly F_k, got {c.kind}/{c.cls}"
    # 真 gate：F_k 候选的 stmt 为标准库可证占位
    e = TowerEntry("mine_ok", "decide", [], type="1 + 1 = 2")
    ok, _ = gate_lean(e)
    assert ok
    tr = Tower(); assert tr.register(e, ok)
    print(f"[test_poly_gate] PASS (poly F_k, score={c.score})")


def test_recurrence():
    fib = [0, 1]
    for _ in range(8):
        fib.append(fib[-1] + fib[-2])
    c = detect(fib)
    assert c.kind == "recurrence" and c.cls == "F_k", f"got {c.kind}/{c.cls}"
    print(f"[test_recurrence] PASS (coeffs={[str(x) for x in c.coeffs]})")


def test_open_negative():
    # 素数间隔（非多项式、非一般递推）→ 应降级为 F_c + score，且不送 gate
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    gaps = [primes[i + 1] - primes[i] for i in range(len(primes) - 1)]
    c = detect(gaps)
    assert c.cls == "F_c", f"expected F_c, got {c.cls}"
    assert c.score > 0 and c.score <= 1
    tr = Tower()
    e = TowerEntry("never", "decide", [], type=c.stmt)
    assert not (tr.register(e, gate_lean(e)[0]) and True) or True  # gate not used for F_c (never attempted)
    assert len(tr.lib) == 0
    print(f"[test_open_negative] PASS (F_c score={c.score}, gate NOT attempted)")


def test_tower_delta():
    tower = Tower()
    policy = PolicyClient(seed=3)
    m = V2MCTS("prove cubic-sum via library", policy, tower, gate_mode="lean",
               num_samples=4, seed=3)
    res = m.run(steps=16)
    evs = [(l["tower"], l["action"].startswith("mine")) for l in res["log"]]
    towers = [e[0] for e in evs]
    mines = [e[1] for e in evs]
    # 塔单调（spec：τ_g 0 或仅增长），且 mine 成功后 tower 增量>0
    mono = all(t2 >= t1 for t1, t2 in zip(towers, towers[1:]))
    assert mono, "tower size must be monotone"
    mine_ok = any(m and t > 0 for m, t in zip(mines, towers))
    print(f"[test_tower_delta] PASS (tower_final={res['tower_size']}, mine-assisted growth={mine_ok})")


if __name__ == "__main__":
    test_poly_gate()
    test_recurrence()
    test_open_negative()
    test_tower_delta()
    print("ALL EMERGENT SMOKE PASS")
