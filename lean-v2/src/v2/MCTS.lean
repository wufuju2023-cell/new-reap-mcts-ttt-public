/-
v2/MCTS.lean — 自包含 MCTS 引擎（纯 std Lean；节点=类型化状态+观测，动作=参数化实例）。
语义参照原始 reap 实现（TreeSearch/MCTS.lean + Tactic/TreeSearch.lean 的 PUCT/backup），
但此处以“多轮工具调用”所需的最小正规化形式重写：T1(obs∈state) T2(param-action) T4(tower∈node)。
-/
import v2.Effect

namespace v2

structure Obs (ε : Type) where
  value : ε
  ok : Bool
  trace : String := ""
  deriving Repr, Inhabited

structure TowerNodeEntry where
  name : String
  body : String
  deps : Array String
  deriving Repr, Inhabited

structure TowerNode where
  lib : Array TowerNodeEntry := #[]
  deriving Repr, Inhabited

def TowerNode.height (t : TowerNode) : Nat :=
  t.lib.foldl (fun h e =>
    let d := e.deps.foldl (fun acc n => if t.lib.any (fun x => x.name == n) then acc + 1 else acc) 0
    max h d) 0

/-- 搜索节点状态：T1 结构——上下文+观测+OK+塔（库快照）。 -/
structure S where
  ctx : String
  obs : Obs Int
  tower : TowerNode
  deriving Repr, Inhabited

/--
Action：T2 参数化动作（与上游 MetaActions.lean 对齐，但参数为类型化值：
effect 的参数 inVals 由策略/计划器给出——不再由搜索器随意生成）。
-/
inductive Action where
  | effect (spec : EffSpec)
  | adddecl (e : TowerNodeEntry)
  | mine (series : Array Int)
  | patch (src : String) (to : String)
  | fillhole (hole : Nat) (term : String)
  deriving Repr, Inhabited

namespace Action

def toString : Action → String
  | .effect s => s!"effect({s.name}:{s.verifier})"
  | .adddecl e => s!"adddecl({e.name})"
  | .mine series => s!"mine({series.size} obs)"
  | .patch a b => s!"patch({a}→{b})"
  | .fillhole h t => s!"fillhole({h}:{t})"

def toKey : Action → String := toString

end Action

/-- 转移器：由外部实现（Lean 执行器 / gate / 未来 HTTP）。 -/
abbrev EnvFn := S → Action → S   -- 确定性转移器（仅演示/正名；网络/IO 适配层将在后续子模块替换）

/-- 树节点（固定于 stack 上的迭代实现见 MCTS），此处为可证纯结构。 -/
structure Node where
  state : S
  prior : Float
  numVisit : Nat := 0
  valueSum : Float := 0.0
  mut? : Bool := false
  deriving Repr, Inhabited

end v2
