/-
Reap.Training.RolloutSink — JSONL 样本面（spec 02）：原子追加、无 UI 依赖。
纯 Lean4 std（IO + Json），可独立编译；由 batch 驱动调用。
-/
import Reap.Training.Verdict
import Lean.Data.Json

namespace Reap.Training

open Lean

structure NodeEvent where
  taskId : String
  treeHash : String
  nodeIdx : Nat
  parentIdx : Nat
  depth : Nat
  state (statePp : String) : String := statePp
  stateKey : String
  goalCount : Nat
  partialGoal : Int
  tactic : String
  verdict : Verdict
  logprobAvg : Float
  sampleIdx : Nat
  value : Float
  wasSolved : Bool
  deriving Repr, Inhabited

instance : ToJson NodeEvent where
  toJson e := json% {
    "kind": "node_visited",
    "task_id": $(e.taskId),
    "tree_hash": $(e.treeHash),
    "node_idx": $(e.nodeIdx),
    "parent_idx": $(e.parentIdx),
    "depth": $(e.depth),
    "state_pp": $(e.state ""),
    "state_key": $(e.stateKey),
    "goal_count": $(e.goalCount),
    "partial_goal": $(e.partialGoal),
    "tactic": $(e.tactic),
    "verdict": $(e.verdict),
    "policy": { "logprob_avg": $(e.logprobAvg), "n_samples": 6, "sample_idx": $(e.sampleIdx) },
    "value": { "score": $(e.value), "source": "policy_server" },
    "was_solved": $(e.wasSolved)
  }

structure TaskDoneEvent where
  taskId : String
  solved : Bool
  reason : String := ""
  treeHash : String := ""
  script : Option String := none
  stats : String := "{}"
  deriving Repr, Inhabited

instance : ToJson TaskDoneEvent where
  toJson e := json% {
    "kind": "task_done",
    "task_id": $(e.taskId),
    "solved": $(e.solved),
    "reason": $(e.reason),
    "tree_hash": $(e.treeHash),
    "script": $(e.script),
    "stats": $(e.stats)
  }

structure RtttUpdateEvent where
  taskId : String
  loss : Float
  kl : Float
  deriving Repr, Inhabited

instance : ToJson RtttUpdateEvent where
  toJson e := json% {
    "kind": "rttt_update",
    "task_id": $(e.taskId),
    "loss": $(e.loss),
    "kl": $(e.kl)
  }

/-- 追加一行（原子写：单 putStrLn + flush；路径目录由调用方保证） -/
def appendJson (path : System.FilePath) (j : Json) : IO Unit := do
  IO.FS.withFile path .append fun h => do
    h.putStrLn (j.compress)
    h.flush

def appendNode (path : System.FilePath) (e : NodeEvent) : IO Unit :=
  appendJson path (toJson e)

def appendDone (path : System.FilePath) (e : TaskDoneEvent) : IO Unit :=
  appendJson path (toJson e)

def appendRttt (path : System.FilePath) (e : RtttUpdateEvent) : IO Unit :=
  appendJson path (toJson e)

end Reap.Training
