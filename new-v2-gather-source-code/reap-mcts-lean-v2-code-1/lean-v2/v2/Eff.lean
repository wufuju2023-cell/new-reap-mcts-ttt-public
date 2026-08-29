/-
v2/Eff.lean — Eff 通道（spec 01）：类型化效应原语。
纯 Lean std；可独立编译。分类：DeterministicE / ExistentialE。
-/
import Lean.Data.Json

namespace v2

open Lean

inductive EffClass where
  | deterministic | existential
  deriving Repr, DecidableEq

instance : ToString EffClass where
  toString
  | .deterministic => "deterministic"
  | .existential => "existential"

structure EffSpec where
  name : String
  inVals : Array Int
  verifier : String           -- 独立可裁决的判定代码（如 "sq-sum-check"）
  klass : EffClass := .deterministic
  deriving Repr, Inhabited

instance : ToJson EffSpec where
  toJson e := json% {
    "name": $(e.name),
    "in_vals": $(e.inVals),
    "verifier": $(e.verifier),
    "class": $(toString e.klass)
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

/-- DeterministicE 白名单执行器（纯 Int 计算；ExistentialE 一律拒绝，除非显式白名单）。 -/
def runEffect (spec : EffSpec) : EffObs :=
  if spec.klass == .existential then
    ⟨0, false, "existential effects disabled by default"⟩
  else
    match spec.verifier with
    | "sqsum-check" =>
        let s := spec.inVals.foldl (fun acc x => acc + x * x) 0
        if s == 0 then ⟨0, true, "sqsum: zeros"⟩ else ⟨s, true, "sqsum: ok"⟩
    | "arith-check" =>
        let s := spec.inVals.foldl (fun acc x => acc + x) 0
        ⟨s, true, "arith: ok"⟩
    | _ => ⟨0, false, "unknown verifier"⟩

end v2
