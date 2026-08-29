#!/usr/bin/env python3
"""v1_sink.py — RolloutSink JSONL 样本面（schema 校验 + 原子追加）
依 spec: explain/reap-mcts-lean-v1/02-rollout-sink.md
"""
import json, hashlib, os, time

ALLOWED_KINDS = {"node_visited", "task_done", "rttt_update"}
VERDICT_CLASSES = {"ok", "parse", "forbidden", "timeout", "errorMsgs",
                   "unassigned", "aux", "kernel", "infra_error"}

class Sink:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def node_visited(self, *, task_id, node_idx, parent_idx, depth, state_pp,
                     state_key, goal_count, partial_goal, tactic, verdict,
                     logprob_avg, sample_idx, value, was_solved, tree_hash):
        rec = {"kind": "node_visited", "task_id": task_id, "ts": time.strftime("%FT%TZ", time.gmtime()),
               "tree_hash": tree_hash, "node_idx": node_idx, "parent_idx": parent_idx,
               "depth": depth, "state_pp": state_pp, "state_key": state_key,
               "goal_count": goal_count, "partial_goal": partial_goal, "tactic": tactic,
               "verdict": {"class": verdict, "kernel_check": verdict == "ok"},
               "policy": {"logprob_avg": logprob_avg, "n_samples": 6, "sample_idx": sample_idx},
               "value": {"score": value, "source": "policy_server"},
               "was_solved": was_solved}
        self._append(rec)

    def task_done(self, *, task_id, solved, script=None, reason="", tree_hash="", stats=None):
        rec = {"kind": "task_done", "task_id": task_id, "ts": time.strftime("%FT%TZ", time.gmtime()),
               "solved": solved, "reason": reason, "tree_hash": tree_hash,
               "script": script if solved else None, "stats": stats or {}}
        self._append(rec)

    def rttt_update(self, *, task_id, loss, kl, state=""):
        self._append({"kind": "rttt_update", "task_id": task_id,
                      "ts": time.strftime("%FT%TZ", time.gmtime()), "loss": loss, "kl": kl})

    def _append(self, rec):
        if rec["kind"] not in ALLOWED_KINDS:
            raise ValueError(f"bad kind {rec['kind']}")
        if rec["kind"] == "node_visited" and rec["verdict"]["class"] not in VERDICT_CLASSES:
            raise ValueError(f"bad verdict {rec['verdict']['class']}")
        line = json.dumps(rec, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def state_key(state_pp: str) -> str:
    return "sha256:" + hashlib.sha256(state_pp.encode()).hexdigest()

def main():
    # CLI: v1_sink.py --validate <file> 校验既有文件 schema
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "--validate":
        ok = bad = 0
        with open(sys.argv[2]) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    assert rec["kind"] in ALLOWED_KINDS
                    if rec["kind"] == "node_visited":
                        assert rec["verdict"]["class"] in VERDICT_CLASSES
                    ok += 1
                except Exception:
                    bad += 1
        print(f"valid={ok} broken={bad}")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
