/-
v2/MetaActions.lean — 元动作空间（spec 02）：fillhole / patch / adddecl / effect。
动作合法性 = 类型检查（此处以纯数据类型表示；Lean 侧的 typecheck 由外部 kernel 承担）。
-/
import Lean.Data.Json
import v2.Eff
import v2.Tower

namespace v2

open Lean

inductive Action where
  | fillhole (hole : Nat) (term : String)
  | patch (expr : String) (by_ : String) (to : String)  -- 抽象/特化替换
  | adddecl (entry : TowerEntry)
  | effect (spec : EffSpec)
  deriving Repr, Inhabited

instance : ToString Action where
  toString
  | .fillhole h t => s!"fillhole({h}:{t})"
  | .patch e b t => s!"patch({b}→{t} in {e})"
  | .adddecl e => s!"adddecl({e.name})"
  | .effect s => s!"effect({s.name})"

instance : ToJson Action where
  toJson
  | .fillhole h t => json% {"kind":"fillhole","hole":$(h),"term":$(t)}
  | .patch e b t => json% {"kind":"patch","expr":$(e),"from":$(b),"to":$(t)}
  | .adddecl e => json% {"kind":"adddecl","entry":$(e)}
  | .effect s => json% {"kind":"effect","spec":$(s)}

/-- 合法谓词的纯函数模拟：effect 仅允许 Determinstic；adddecl 需要 TOWER_GATE（外部）——此处以 flag 表示。 -/
def Action.legalDummy (a : Action) (towerGate : Nat) : Nat :=
  towerGate

end v2
