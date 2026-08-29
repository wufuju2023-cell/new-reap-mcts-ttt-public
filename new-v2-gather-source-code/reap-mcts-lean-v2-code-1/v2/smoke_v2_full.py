"""smoke_v2_full.py — V2 完整冒烟（code-1 全部切片接线）：
① gate_lean 真容器验证（std 命题 ok/错命题 reject）② policy_client 采样（mock 端点）
③ MCTS 主循环（PUCT + gate + tower 单调）全链跑通。
"""
import os
import tempfile

from v2.gate_lean import gate_lean
from v2.tower import Tower, TowerEntry
from v2.policy_client import PolicyClient
from v2.mcts_loop import V2MCTS


def test_gate_real():
    e_ok = TowerEntry("lem_ok", "decide", [], type="1 + 1 = 2")
    e_bad = TowerEntry("lem_bad", "by exact 2", [], type="1 + 1 = 3")
    ok1, _ = gate_lean(e_ok)
    ok2, _ = gate_lean(e_bad)
    assert ok1, "real gate should accept decide"
    assert not ok2, "real gate should reject wrong proof"
    print("[test_gate_real] PASS (ok=accept, wrong=reject)")


def test_mcts_full(gate_mode: str = "mock"):
    tower = Tower()
    policy = PolicyClient(seed=7)
    m = V2MCTS("prove 1+1=2 via library", policy, tower, gate_mode=gate_mode, num_samples=4, seed=7)
    res = m.run(steps=12)
    assert res["nodes"] >= 1
    assert tower.height() >= 0
    # 塔高度与规模日志单调性检查
    hs = [l["h"] for l in res["log"]]
    assert hs == sorted(hs), "tower height must be monotone"
    print(f"[test_mcts_full:{gate_mode}] PASS (tower={res['tower_size']}, h={res['tower_height']}, nodes={res['nodes']})")


if __name__ == "__main__":
    test_gate_real()
    test_mcts_full("mock")
    # 真 gate 模式（更慢，但验证与 lean 容器接线）
    test_mcts_full("lean")
    print("ALL V2 FULL SMOKE PASS")
