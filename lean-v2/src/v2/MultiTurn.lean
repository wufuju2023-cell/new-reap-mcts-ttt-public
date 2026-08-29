/-
v2/MultiTurn.lean — 多轮工具调用的顺序执行子程序（T3）。
EffectSubroutine(P) 是树的“单一动作”；内部 = 一轮一轮执行 Lean `while` 循环：
  policy建议 → run(Enf) → obs并入S（T1 在此发生）→ 循环继续 → Ḡ 终局或预算耗尽。
纯 std Lean：不 import Reap；可独立编译（与容器无关，本机 lean 直编）。
-/
import v2.MCTS

namespace v2

/-- T3：一步执行一个 action，返回新状态（确定性执行器；网络/IO 适配层后续替换）。 -/
def runStep (env : EnvFn) (s : S) (a : Action) : S := env s a

/-- EffectSubroutine：顺序执行 m 轮（含预算；foldl 无递归）。 -/
structure SubroutineResult where
  final : S
  rounds : Nat
  towerH : Nat
  ok : Bool
  deriving Repr, Inhabited

def runSubroutine (env : EnvFn) (s0 : S) (actions : Array Action) (budget : Nat) : SubroutineResult :=
  let seq := actions.take budget
  let final := seq.foldl (fun s a => runStep env s a) s0
  { final := final,
    rounds := seq.size,
    towerH := final.tower.height,
    ok := final.obs.ok }

/-- 简单的 PUCT 选择（自包含；与上游 c_init/c_base 常数一致）。 -/
def puctScore (prior : Float) (N : Nat) (n : Nat) (Q : Float) : Float :=
  let c := 1.0 + Float.log ((Nat.toFloat N + 3200.0 + 1.0) / 3200.0)
  let u := c * prior * Float.sqrt (Nat.toFloat N) / (Nat.toFloat n + 1.0)
  Q + u

end v2
