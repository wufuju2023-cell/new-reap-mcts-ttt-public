"""smoke_v2.py — V2 code-1 端到端冒烟：
① Eff 白名单判定（Deterministic OK / Existential 拒绝）
② gate 受控入塔：ok→L 增长+深度/塔高单调；reject→不增长
③ 样本 sink 兼容性（v1 kind 扩展）
"""
import os
import tempfile

from v2.eff_registry import EffSpec, EffClass, lookup, public_verifiers
from v2.tower import Tower, TowerEntry
from v2.runner import V2Harness, V2State


def test_eff():
    assert public_verifiers() == ["sqsum-check", "arith-check"]
    r1 = lookup(EffSpec("a", [1, 2, 3], "sqsum-check", EffClass.DETERMINISTIC))
    assert r1.ok and r1.value == 14
    r2 = lookup(EffSpec("b", [1, 1], "arith-check", EffClass.DETERMINISTIC))
    assert r2.ok and r2.value == 2
    r3 = lookup(EffSpec("c", [1], "sqsum-check", EffClass.EXISTENTIAL))
    assert not r3.ok and "disabled" in r3.trace
    r4 = lookup(EffSpec("d", [1], "unknown-verifier", EffClass.DETERMINISTIC))
    assert not r4.ok
    print("[test_eff] PASS")


def test_tower():
    tr = Tower()
    e1 = TowerEntry("lem1", "by omega", [])
    e2 = TowerEntry("lem2", "by simp", ["lem1"])
    e3 = TowerEntry("lem3", "by nlinarith", ["lem1", "lem2"])
    assert not tr.register(e1, False)          # gate reject -> 不入
    assert tr.register(e1, True) and len(tr.lib) == 1
    assert tr.register(e2, True) and len(tr.lib) == 2
    assert tr.depth(e2) == 1                    # 引用 lem1（已在库）
    assert tr.register(e3, True)
    assert tr.height() == 2                     # τ_g 单调（lem3 深 2）
    print("[test_tower] PASS")


def test_harness_sink():
    sink = os.path.join(tempfile.gettempdir(), "v2_smoke_sink.jsonl")
    if os.path.exists(sink):
        os.unlink(sink)
    h = V2Harness(gate=lambda e: "broken" not in e.name, sink_path=sink)
    st = V2State(goal="g", tower=Tower())
    h.step(st, "effect:arith-check")
    h.step(st, "adddecl:lem_a~by rfl")
    h.step(st, "adddecl:broken~by sorry_unsafe")
    recs = [json.loads(x) for x in open(sink)]
    kinds = {r["kind"] for r in recs}
    assert "effect" in kinds and "tower" in kinds and "tower_reject" in kinds and len(st.tower.lib) == 1
    print("[test_harness_sink] PASS (kinds:", sorted(kinds), ")")


if __name__ == "__main__":
    import json  # noqa: F401  (used inside harness)
    test_eff()
    test_tower()
    test_harness_sink()
    print("ALL V2 SMOKE PASS")
