/-
v2/Effect.lean — 类型化效应原语（CPU 侧 Lean 模块，纯 std 可编译）。
对齐 spec：多轮tool-call/00；EffObs 将进入搜索状态（T1）。
-/
import Lean.Data.Json

namespace v2

open Lean

inductive EffClass where
  | deterministic | existential
  deriving Repr, DecidableEq, Inhabited

instance : ToString EffClass where
  toString
  | .deterministic => "deterministic"
  | .existential => "existential"

instance : ToJson EffClass where
  toJson
  | .deterministic => json% "deterministic"
  | .existential => json% "existential"

structure EffSpec where
  name : String
  inVals : Array Int
  verifier : String
  klass : EffClass := .deterministic
  deriving Repr, Inhabited

instance : ToJson EffSpec where
  toJson e := json% {
    "name": $(e.name),
    "in_vals": $(e.inVals),
    "verifier": $(e.verifier),
    "class": $(e.klass)
  }

structure EffObs where
  value : Int
  ok : Bool
  trace : String := ""
  deriving Repr, Inhabited

instance : ToJson EffObs where
  toJson o := json% {
    "value": $(o.value),
    "ok": $(o.ok),
    "trace": $(o.trace)
  }

/-- 效果执行器（白名单）；Existential 默认禁用（§8 工程红线：不可证的效果不作证据）。 -/
def runEffect (spec : EffSpec) : EffObs :=
  if spec.klass == .existential then
    ⟨0, false, "existential effects disabled by default"⟩
  else
    match spec.verifier with
    | "sqsum-check" =>
        let s := spec.inVals.foldl (fun acc x => acc + x * x) 0
        ⟨s, true, "sqsum: ok"⟩
    | "arith-check" =>
        let s := spec.inVals.foldl (fun acc x => acc + x) 0
        ⟨s, true, "arith: ok"⟩
    | _ => ⟨0, false, "unknown verifier"⟩

end v2
