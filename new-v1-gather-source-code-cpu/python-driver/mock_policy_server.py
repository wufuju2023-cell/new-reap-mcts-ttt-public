#!/usr/bin/env python3
"""mock_policy_server.py — CPU 端 mock（V1 本地端到端用；GPU 端由 policy_server.py 替换）
端点: /v1/chat/completions  /value  /health  /premises
"""
import json, random, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TACTICS = ["simp", "omega", "nlinarith", "exact h₀", "apply Nat.div_dvd_of_dvd"]
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8760

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        self._json(200, {"ok": True, "mode": "mock-cpu"})
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        p = self.path
        if p.endswith("/chat/completions"):
            k = body.get("n", 6)
            choices = [{"text": random.choice(TACTICS),
                        "logprob_avg": round(random.uniform(-18.0, -2.0), 3)} for _ in range(k)]
            self._json(200, {"choices": choices})
        elif p.endswith("/value"):
            self._json(200, {"score": round(random.uniform(0.0, 1.0), 4)})
        elif p.endswith("/premises"):
            self._json(200, [{"formal_name": "Nat.div_dvd_of_dvd", "formal_statement": "…"}])
        else:
            self._json(404, {"error": p})

if __name__ == "__main__":
    print(f"[mock-policy] :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
