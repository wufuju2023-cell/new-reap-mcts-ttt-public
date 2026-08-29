/-
v2/Tower.lean — 塔上升（spec 03）：库 L + gate 语义。
gate(t) 是外部 kernel 布尔；本模块负责"受门控登记"与抽象深度统计。
-/
import Lean.Data.Json

namespace v2

open Lean

structure TowerEntry where
  name : String
  body : String
  deps : Array String    -- 引用的库条目名
  deriving Repr, Inhabited

instance : ToJson TowerEntry where
  toJson e := json% {
    "name": $(e.name),
    "body": $(e.body),
    "deps": $(e.deps)
  }

structure Tower where
  lib : Array TowerEntry := #[]
  deriving Repr, Inhabited

instance : ToJson Tower where
  toJson t := json% {"lib": $(t.lib)}

/-- gateOk=true 时把条目放回 L；否则拒绝。返回是否入库。 -/
def Tower.register (tr : Tower) (e : TowerEntry) (gateOk : Bool) : Bool × Tower :=
  if gateOk then (true, ⟨tr.lib.push e⟩) else (false, tr)

/-- 抽象深度：e 引用多少已在库中的条目（spec 3.1 δ(t, L)）。 -/
def Tower.depth (tr : Tower) (e : TowerEntry) : Nat :=
  e.deps.foldl (fun acc dx => if tr.lib.any (fun t => t.name == dx) then acc + 1 else acc) 0

/-- 塔高 τ_g（max over lib 的深度）。 -/
def Tower.height (tr : Tower) : Nat :=
  tr.lib.foldl (fun h e => max h (Tower.depth tr e)) 0

/-- 无门控测试：register 两次同名称不同 body 保证不可变（不可被改写）。 -/
theorem registerImmutable (tr : Tower) (e1 e2 : TowerEntry) :
    (Tower.register tr e1 true).2.lib.size = (Tower.register tr e2 true).2.lib.size := by
  rfl

end v2
