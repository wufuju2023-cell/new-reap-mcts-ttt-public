"""v2/policy_client.py — V2 策略客户端（OpenAI 兼容端点；mock 回退）。
端点返回“元动作”文本（fillhole/patch/adddecl/effect）；与 mock/v2 模式或 GPU policy_server 对齐。
"""
import json
import random
import urllib.request

MOCK_ACTIONS = [
    "effect:arith-check", "effect:sqsum-check",
    "adddecl:1 + 1 = 2~decide", "adddecl:2 * 2 = 4~decide",
    "adddecl:9 = 9~rfl",
    "mine:series",
    "patch:∀→∃", "fillhole:h0",
]

DEFAULT_ENDPOINT = "http://127.0.0.1:8760"


class PolicyClient:
    def __init__(self, endpoint: str = "", num_samples: int = 4, seed: int = 42):
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        self.num_samples = num_samples
        self.rng = random.Random(seed)
        self.mode = self._probe()

    def _probe(self) -> str:
        try:
            req = urllib.request.Request(self.endpoint + "/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                body = json.loads(r.read())
                return "v2" if body.get("mode") == "mock-cpu" else "gpu"
        except Exception:
            return "mock-local"

    def sample(self, prompt: str, n: int | None = None) -> list[tuple[str, float]]:
        n = n or self.num_samples
        if self.mode == "mock-local":
            choices = [(random.choice(MOCK_ACTIONS),
                        round(random.uniform(-14.0, -2.0), 3)) for _ in range(n)]
            return choices
        try:
            req = urllib.request.Request(
                self.endpoint + "/v1/chat/completions",
                data=json.dumps({"prompt": prompt, "n": n, "temperature": 0.99}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
            return [(c["text"], c.get("logprob_avg", -12.0)) for c in d.get("choices", [])]
        except Exception:
            return [("effect:arith-check", -8.0)] * n
