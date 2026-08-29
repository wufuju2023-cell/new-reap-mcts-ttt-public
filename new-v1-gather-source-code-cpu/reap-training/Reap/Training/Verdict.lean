/-
Reap.Training.Verdict — V1 结构化验证结论（spec: explain/reap-mcts-lean-v1/02）
纯 Lean4 标准库依赖（不 import Reap），任何 Lean 4.28 环境可独立编译。
-/
import Lean.Data.Json

namespace Reap.Training

open Lean

inductive VerdictClass where
  | ok | parse | forbidden | timeout | errorMsgs | unassigned | aux | kernel | infraError
  deriving DecidableEq, Repr

instance : ToString VerdictClass where
  toString
  | .ok => "ok"
  | .parse => "parse"
  | .forbidden => "forbidden"
  | .timeout => "timeout"
  | .errorMsgs => "errorMsgs"
  | .unassigned => "unassigned"
  | .aux => "aux"
  | .kernel => "kernel"
  | .infraError => "infra_error"

instance : ToJson VerdictClass where
  toJson v := json% {"class": $(toString v)}

structure Verdict where
  class_ : VerdictClass
  messages : String := ""
  kernelCheck : Bool := false
  deriving Repr

instance : Inhabited Verdict where
  default := ⟨.ok, "", false⟩

instance : ToJson Verdict where
  toJson v := json% {
    "class": $(toString v.class_),
    "messages": $(v.messages),
    "kernel_check": $(v.kernelCheck)
  }

/-- 由字符串分类（服务端已验证的判定来源），kernelCheck 仅 ok 时允许为真 -/
def Verdict.ofClass (cls : VerdictClass) (messages : String := "") (kernel : Bool := false) : Verdict :=
  ⟨cls, messages, kernel ∧ (cls == .ok)⟩

end Reap.Training
