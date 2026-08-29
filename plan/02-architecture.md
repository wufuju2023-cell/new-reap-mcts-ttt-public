# 02. Architecture

## 2.1 Components

```
┌─────────────────────────────────────────────────────────────┐
│ Lean 4 (this laptop / lean server)                          │
│   theorem ... := by                                          │
│     reap!!        ← orchestrates search (already built)      │
│     │                                                        │
│     ├─ policy HTTP   → policy_server (vLLM, small model)     │
│     ├─ value HTTP    → value_server  (LLM-JSON or head)      │
│     └─ premises HTTP → ps_server     (retriever, phase C:    │
│                                             Lean-side native)│
└──────────┬───────────────────────────────────────────────────┘
           │ rollouts: JSONL (state, tactic, logprob, value,
           │            rollout return, solved flag...)
           ▼
┌─────────────────────────────────────────────────────────────┐
│ Trainer (Python, rented GPU)                                │
│   SFT → serve → rollouts → GRPO/PPO update → save adapter   │
│   → hot-reload policy_server → repeat                       │
└─────────────────────────────────────────────────────────────┘
```

## 2.2 Interface contracts (must match Reap's code)

- **Policy** — OpenAI chat completions, needs `logprobs = true`
  (`Reap/Tactic/Generator.lean:102`):
  ```json
  POST /v1/chat/completions
  { "messages": [ {"role": "user", "content": "<state + premises>"} ],
    "n": 6, "max_tokens": 1024, "temperature": 0.99, "logprobs": true }
  → choices[].message.content = tactic string, choices[].logprobs.content[].logprob
  ```
  Sum of token logprobs = $\log p$ of the tactic (policy as *sequence model*).
- **Value** — chat completion, `n=1`, content must parse as
  `{"score": <float>}` (`Generator.lean:127-144`). Internally the code negates:
  search minimizes score, i.e. $V_{\text{search}} = - \text{score}$.
- **Premise selection** — `POST <ps_endpoint>` body
  `{"query": <state>, "num_results": n}` returns array of
  `{"formal_name", "formal_statement"}` (`Reap/PremiseSelection/API.lean`).

## 2.3 Model choices

| Role | Phase A (smoke) | Phase B (main) | Notes |
|---|---|---|---|
| Policy | any tiny model served by vLLM, or **mock endpoint** | Qwen2.5-Math-1.5B/3B LoRA | must emit `logprobs` |
| Value | mock `{"score": 0.5}` | LLM-prompt value (phase B2) then MLP head (phase B3) | head needs custom serving |
| PS | mock / Lean-native suggestions | Lean-native `set_library_suggestions` | skip network retriever |

Mock endpoints are *valuable*: they let the whole Lean harness run without any
GPU — great for verifying the harness before spending money.

## 2.4 Serving with parameter hot-swap

- Policy server = vLLM with a LoRA adapter per checkpoint (`--enable-lora`,
  `--max-lora-rank`). Updates do not restart the server: swap `--lora-modules`.
- Value-head option: own FastAPI server; pipeline = frozen backbone
  embedding + trainable head $V_\phi$:

$$
V_\phi(s) = W_2 \cdot \mathrm{act}(W_1 \cdot h(s))
$$

  serving `{"score": -V_phi}` through the same chat JSON wrapper, or a second
  endpoint wired into a small harness patch (only if measuring head advantage).

## 2.5 Priorities

1. Reuse Reap verbatim first (zero code changes, mock+real endpoints).
2. Only if the chat-JSON value proves too crude: patch Reap to call a
   value endpoint that returns a scalar directly (small, contained diff).
3. Everything below the Lean boundary is Python; every file it emits is JSONL.
