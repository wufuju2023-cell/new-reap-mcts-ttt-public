/-
v2/Demo.lean — 本机（无容器）多轮工具调用 × MCTS 演示：
T1 观测入状态 / T2 参数化动作 / T3 EffectSubroutine / T4 塔∈状态 / T5 占位(gate 纯函数)。
运行：PATH=$HOME/lean428/lean/bin:$PATH lean --run src/v2/Demo.lean
-/
import v2.MultiTurn
import v2.Effect

namespace v2

open Lean

def demoEnv : EnvFn := fun s a =>
  match a with
  | .effect spec =>
      let obs := runEffect spec
      { s with obs := { value := obs.value, ok := obs.ok, trace := obs.trace } }
  | .adddecl e =>
      let old := s.tower
      let ok := e.deps.all (fun d => old.lib.any (fun x => x.name == d))
      { s with tower := { lib := if ok then old.lib.push e else old.lib } }
  | .mine series =>
      let sum := series.foldl (fun acc x => acc + x) 0
      { s with obs := ⟨sum, true, "mine:sum-ok"⟩ }
  | .patch _ _ | .fillhole _ _ =>
      { s with obs := ⟨0, true, "meta:no-op-sim"⟩ }

def runDemo : IO Unit := do
  -- 初始状态：ctx + 空观测 + 空塔
  let s0 : S := ⟨"goal: sum of squares", ⟨0, false, ""⟩, ⟨#[]⟩⟩
  -- 多轮动作序列（T3：顺序执行，a2 依赖 a1 的观测轨道由 demoEnv 建模）
  let actions : Array Action :=
    #[ .effect ⟨"experiment-1", #[1, 2, 3], "sqsum-check", .deterministic⟩,
       .effect ⟨"experiment-2", #[2, 2, 2], "arith-check", .deterministic⟩,
       .adddecl ⟨"sq3", "9", #["sq3"]⟩,           -- deps 引用自身→gate 应为否（演示 T4 门控）
       .adddecl ⟨"lem1", "9", #[]⟩,
       .mine #[0, 1, 4, 9] ]
  let res := runSubroutine demoEnv s0 actions (budget := 5)
  IO.println s!"rounds={res.rounds} towerH={res.towerH} ok={res.ok}"
  IO.println s!"final.obs = {res.final.obs.value} ok={res.final.obs.ok} trace={res.final.obs.trace}"
  IO.println s!"lib = {res.final.tower.lib.map (fun e => e.name)}"
  -- PUCT 选择演示
  IO.println s!"puct(prior=0.3, N=8, n=1, Q=0.4) = {puctScore 0.3 8 1 0.4}"

end v2

def main : IO Unit := v2.runDemo
