"""CPU-only contract tests for the scalar value head.

These tests deliberately operate on precomputed hidden states.  They do not
load a Hugging Face checkpoint or require a CUDA device, so they can run in a
small CI worker as well as in the policy-server image.
"""

from __future__ import annotations

import io
import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import torch
from torch.nn import functional as F

from app.value_head import (
    VALUE_HEAD_SCHEMA,
    ValueHead,
    ValueHeadTrainer,
    discounted_returns,
    last_token_hidden,
    load_value_head,
    model_hidden_size,
    proof_depth_to_target,
    save_value_head,
)
from app.train_value_head import iter_examples


class _Config:
    hidden_size = 13


class _ModelWithConfig:
    config = _Config()


class _ModelWithEmbeddings:
    config = object()

    class _Embeddings:
        embedding_dim = 7

    def get_input_embeddings(self):
        return self._Embeddings()


class _TinyEncoding(dict):
    """Minimal ``BatchEncoding`` replacement used by policy-server tests."""

    def to(self, device):
        for key, value in self.items():
            if torch.is_tensor(value):
                self[key] = value.to(device)
        return self


class _TinyTokenizer:
    eos_token = "<eos>"
    eos_token_id = 0
    pad_token_id = 0

    def __call__(self, text, return_tensors="pt"):
        del return_tensors
        # Distinct, deterministic one-token prompts keep the mock model tiny.
        token = (len(str(text)) % 7) + 1
        return _TinyEncoding(
            input_ids=torch.tensor([[token]], dtype=torch.long),
            attention_mask=torch.ones(1, 1, dtype=torch.long),
        )

    def decode(self, ids, skip_special_tokens=True):
        del skip_special_tokens
        return "".join(str(int(token)) for token in ids)


class _TinyPolicyModel(torch.nn.Module):
    """CPU policy stand-in exposing hidden states, loss, and state_dict."""

    def __init__(self, hidden_size=4):
        super().__init__()
        self.scale = torch.nn.Parameter(torch.tensor(0.1))
        self.hidden_size = hidden_size
        self.config = types.SimpleNamespace(use_cache=False)

    def forward(self, input_ids, labels=None, **kwargs):
        del kwargs
        hidden = (
            input_ids.float().unsqueeze(-1).expand(-1, -1, self.hidden_size)
            * self.scale
        )
        # A differentiable but deterministic policy loss is enough to exercise
        # the joint ttt_step backward path.
        loss = (self.scale - 0.1).square()
        if labels is not None:
            loss = loss + labels.float().masked_fill(labels < 0, 0).sum() * 0.0
        return types.SimpleNamespace(
            hidden_states=[hidden],
            last_hidden_state=hidden,
            loss=loss,
        )


class ValueHeadTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(1234)

    def test_dynamic_hidden_size_and_bounded_output(self) -> None:
        """The head must not assume the 4096-wide REAL-Prover backbone."""

        for hidden_size in (3, 13):
            head = ValueHead(hidden_size, hidden_dim=9)
            features = torch.randn(5, hidden_size)
            values = head(features)
            self.assertEqual(tuple(values.shape), (5,))
            self.assertTrue(torch.isfinite(values).all())
            self.assertTrue(bool((values <= 1.0 + 1e-6).all()))
            self.assertTrue(bool((values >= -1.0 - 1e-6).all()))

            # Sequence-shaped hidden states are accepted and use the final
            # position, which mirrors decoder-only model outputs.
            sequence = torch.stack((features, features + 1.0), dim=1)
            torch.testing.assert_close(head(sequence), head(features + 1.0))

        with self.assertRaisesRegex(ValueError, "hidden size mismatch"):
            ValueHead(3, hidden_dim=5)(torch.zeros(2, 4))

    def test_last_token_hidden_is_padding_aware_on_cpu(self) -> None:
        hidden = torch.arange(2 * 4 * 3, dtype=torch.float32).reshape(2, 4, 3)
        # Row 0 is right padded; row 1 is left padded.  Both should select
        # the final *valid* token, not simply hidden[:, -1].
        mask = torch.tensor([[1, 1, 0, 0], [0, 1, 1, 1]], dtype=torch.long)
        selected = last_token_hidden({"last_hidden_state": hidden}, mask)
        torch.testing.assert_close(selected, torch.stack((hidden[0, 1], hidden[1, 3])))

        # A BaseModelOutput-like object and no mask retain the last position.
        output = types.SimpleNamespace(last_hidden_state=hidden)
        torch.testing.assert_close(last_token_hidden(output), hidden[:, -1])

    def test_model_hidden_size_is_architecture_agnostic(self) -> None:
        self.assertEqual(model_hidden_size(_ModelWithConfig()), 13)
        self.assertEqual(model_hidden_size(_ModelWithEmbeddings()), 7)

        with self.assertRaisesRegex(ValueError, "cannot infer"):
            model_hidden_size(object())

    def test_discounted_returns_and_nanoproof_depth_targets(self) -> None:
        # Backward TD/Monte-Carlo return: r[t] + gamma * G[t+1].
        self.assertEqual(discounted_returns([1.0, 0.0, -1.0], gamma=0.5), [0.75, -0.5, -1.0])
        # Scalar head targets are clipped to its tanh range.
        self.assertEqual(discounted_returns([4.0, 4.0], gamma=0.99), [1.0, 1.0])
        self.assertEqual(proof_depth_to_target(0), 0.0)
        self.assertEqual(proof_depth_to_target(64), -1.0)
        self.assertEqual(proof_depth_to_target(100, max_depth=64), -1.0)

        with self.assertRaises(ValueError):
            discounted_returns([0.0], gamma=1.1)
        with self.assertRaises(ValueError):
            proof_depth_to_target(-1)

    def test_mse_update_changes_parameters_and_tracks_examples(self) -> None:
        head = ValueHead(hidden_size=4, hidden_dim=8)
        trainer = ValueHeadTrainer(head, learning_rate=5e-2)
        features = torch.ones(8, 4)
        targets = torch.full((8,), 0.75)

        before_parameters = {k: v.detach().clone() for k, v in head.state_dict().items()}
        before_error = F.mse_loss(head(features).detach(), targets).item()
        result = None
        for _ in range(40):
            result = trainer.update(features, targets)
        assert result is not None
        after_error = F.mse_loss(head(features).detach(), targets).item()

        self.assertLess(after_error, before_error)
        self.assertTrue(any(not torch.equal(before_parameters[k], v) for k, v in head.state_dict().items()))
        self.assertGreaterEqual(result["loss"], 0.0)
        self.assertTrue(torch.isfinite(torch.tensor(result["loss"])))
        self.assertEqual(result["optimizer_steps"], 40.0)
        self.assertEqual(result["examples_seen"], 320.0)
        self.assertAlmostEqual(result["target_mean"], 0.75, places=6)

    def test_update_clamps_targets_and_rejects_bad_batches(self) -> None:
        head = ValueHead(2, hidden_dim=4)
        trainer = ValueHeadTrainer(head, learning_rate=1e-2)
        result = trainer.update(torch.zeros(2, 2), torch.tensor([2.0, -2.0]))
        self.assertAlmostEqual(result["target_mean"], 0.0, places=6)

        with self.assertRaisesRegex(ValueError, "targets length"):
            trainer.update(torch.zeros(2, 2), [0.0])
        with self.assertRaisesRegex(ValueError, "hidden_states"):
            trainer.update(torch.zeros(2, 3), [0.0, 0.0])
        with self.assertRaises(FloatingPointError):
            trainer.update(torch.zeros(2, 2), [float("nan"), 0.0])

    def test_checkpoint_round_trip_restores_head_optimizer_and_counters(self) -> None:
        head = ValueHead(5, hidden_dim=6)
        trainer = ValueHeadTrainer(head, learning_rate=1e-2)
        features = torch.randn(4, 5)
        targets = torch.tensor([0.9, 0.2, -0.3, -0.8])
        for _ in range(3):
            trainer.update(features, targets)

        expected_head = {k: v.detach().clone() for k, v in head.state_dict().items()}
        expected_prediction = head(features).detach().clone()

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "value-head.pt"
            receipt = trainer.checkpoint(path, metadata={"unit": "round-trip"})
            self.assertEqual(receipt["schema_version"], VALUE_HEAD_SCHEMA)
            self.assertTrue(path.is_file())
            self.assertEqual(list(path.parent.glob(".*.tmp")), [])

            restored = ValueHead(5, hidden_dim=6)
            restored_trainer = ValueHeadTrainer(restored, learning_rate=1e-2)
            metadata = load_value_head(path, restored, restored_trainer.optimizer)
            self.assertTrue(metadata["optimizer_loaded"])
            self.assertEqual(metadata["optimizer_steps"], 3)
            self.assertEqual(metadata["examples_seen"], 12)
            self.assertEqual(metadata["metadata"], {"unit": "round-trip"})
            for key, value in expected_head.items():
                torch.testing.assert_close(restored.state_dict()[key], value)
            torch.testing.assert_close(restored(features), expected_prediction)

            # Metadata prevents accidentally applying a head to a differently
            # sized backbone.
            with self.assertRaisesRegex(ValueError, "hidden size mismatch"):
                load_value_head(path, ValueHead(4, hidden_dim=6))

    def test_legacy_raw_state_dict_can_be_migrated(self) -> None:
        head = ValueHead(3, hidden_dim=4)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.pt"
            torch.save(head.state_dict(), path)
            other = ValueHead(3, hidden_dim=4)
            metadata = load_value_head(path, other)
            self.assertTrue(metadata["legacy"])
            for key, value in head.state_dict().items():
                torch.testing.assert_close(other.state_dict()[key], value)

    def test_training_jsonl_preserves_nanoproof_negative_depth_semantics(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "{\"state\":\"s-depth\",\"value_target\":-8}\n"
                "{\"state\":\"s-explicit\",\"value_target\":-0.5}\n"
                "{\"states\":[\"s0\",\"s1\"],\"rewards\":[0,1],\"gamma\":0.99}\n",
                encoding="utf-8",
            )
            rows = list(iter_examples(path))
            self.assertAlmostEqual(rows[0][1], -8.0 / 64.0)
            self.assertAlmostEqual(rows[1][1], -0.5)
            self.assertEqual(rows[2][0], "s0")
            self.assertAlmostEqual(rows[2][1], 0.99)


class EngineAndEndpointMockTests(unittest.TestCase):
    """Exercise policy-server value plumbing without Transformers/PEFT/GPU."""

    @staticmethod
    def _import_policy_server():
        """Import app.policy_server with tiny module stubs when deps are absent."""

        try:
            import app.policy_server as module
            return module
        except ModuleNotFoundError as error:
            if error.name not in {"transformers", "peft"}:
                raise

        transformers = types.ModuleType("transformers")
        transformers.AutoTokenizer = object
        transformers.AutoModelForCausalLM = object
        peft = types.ModuleType("peft")
        peft.LoraConfig = object
        peft.get_peft_model = lambda *args, **kwargs: None
        with patch.dict(sys.modules, {"transformers": transformers, "peft": peft}):
            sys.modules.pop("app.policy_server", None)
            return __import__("app.policy_server", fromlist=["*"])

    class _Encoding(dict):
        def to(self, device):
            return self

    class _Tokenizer:
        def __call__(self, prompt, return_tensors="pt"):
            del return_tensors
            # Keep the encoding deterministic and nonempty, including for an
            # empty prompt (the endpoint should still return a finite score).
            token = max(1, len(prompt))
            return EngineAndEndpointMockTests._Encoding(
                input_ids=torch.tensor([[token]], dtype=torch.long),
                attention_mask=torch.ones(1, 1, dtype=torch.long),
            )

    class _Core:
        def __call__(self, input_ids, output_hidden_states=True, **kwargs):
            del output_hidden_states, kwargs
            # Hidden width is deliberately not 4096.
            hidden = input_ids.float().unsqueeze(-1).repeat(1, 1, 4)
            return types.SimpleNamespace(hidden_states=[hidden])

    class _Model:
        def __init__(self):
            self._core = EngineAndEndpointMockTests._Core()
            self.base_model = types.SimpleNamespace(model=self._core)
            self.training = False

        def eval(self):
            self.training = False
            return self

        def train(self, mode=True):
            self.training = bool(mode)
            return self

        def __call__(self, *args, **kwargs):
            return self._core(*args, **kwargs)

    def _make_engine(self, tmpdir=None):
        """Construct an Engine shell without invoking its HF-heavy __init__."""

        module = self._import_policy_server()
        engine = module.Engine.__new__(module.Engine)
        engine.device = torch.device("cpu")
        engine.tok = _TinyTokenizer()
        engine.model = _TinyPolicyModel(hidden_size=4)
        engine.hidden_size = 4
        engine.vhead = ValueHead(4, hidden_dim=5)
        # No snapshot is written by the tests that omit ``tmpdir``; use a
        # workspace-local directory rather than an unowned TemporaryDirectory
        # object (which would emit a ResourceWarning on interpreter shutdown).
        engine.output_dir = Path(tmpdir) if tmpdir is not None else Path.cwd() / ".value-head-test-out"
        engine.output_dir.mkdir(parents=True, exist_ok=True)
        engine.value_head_path = None
        engine.value_optimizer_steps = 0
        engine.value_examples_seen = 0
        engine.value_coefficient = 1.0
        engine.gamma = 0.5
        engine.max_grad_norm = 1.0
        engine._update_lock = __import__("threading").RLock()
        engine.opt = torch.optim.AdamW(
            list(engine.model.parameters()) + list(engine.vhead.parameters()),
            lr=5e-2,
        )
        engine.generated = 0
        return engine

    def test_engine_value_runs_on_cpu_with_mock_backbone(self) -> None:
        module = self._import_policy_server()
        engine = module.Engine.__new__(module.Engine)
        engine.device = torch.device("cpu")
        engine.tok = self._Tokenizer()
        engine.model = self._Model()
        engine._update_lock = __import__("threading").RLock()
        engine.hidden_size = 4
        engine.vhead = ValueHead(4, hidden_dim=5)

        score = engine.value("cpu mock state")
        self.assertIsInstance(score, float)
        self.assertTrue(-1.0 <= score <= 1.0)

    def test_engine_distance_mode_maps_quality_to_nanoproof_support(self) -> None:
        module = self._import_policy_server()
        engine = module.Engine.__new__(module.Engine)
        engine.value_output_mode = "distance"
        engine.max_distance = 64
        self.assertEqual(engine._score_from_raw(1.0), 1.0)
        self.assertEqual(engine._score_from_raw(-1.0), 64.0)
        self.assertAlmostEqual(engine._score_from_raw(0.0), 32.5)

    def test_engine_target_resolution_supports_td_and_nanoproof_depth(self) -> None:
        engine = self._make_engine()
        self.assertAlmostEqual(engine._target_for_item({"value_target": 0.7}), 0.7)
        self.assertAlmostEqual(engine._target_for_item({"proof_depth": 32}), -0.5)
        # One-step TD: r + gamma * V(next), then clamp to [-1, 1].
        self.assertAlmostEqual(
            engine._target_for_item({"r": 0.4, "next_value": 0.6}), 0.7
        )
        self.assertAlmostEqual(
            engine._target_for_item({"r": 0.4, "next_value": 0.6, "done": True}), 0.4
        )

    def test_engine_ttt_step_updates_value_head_with_explicit_target(self) -> None:
        engine = self._make_engine()
        before = {k: v.detach().clone() for k, v in engine.vhead.state_dict().items()}
        result = engine.ttt_step(
            [{
                "prompt": "state",
                "target": "simp",
                "r": 0.0,
                "logprob_old": 0.0,
                "value_target": 0.8,
            }]
        )
        self.assertEqual(result["value_updates"], 1)
        self.assertEqual(result["steps"], 1)
        self.assertEqual(result["optimizer_steps"], 1)
        self.assertAlmostEqual(result["value_target_mean"], 0.8, places=6)
        self.assertTrue(torch.isfinite(torch.tensor(result["value_loss"])))
        self.assertTrue(
            any(not torch.equal(before[k], v) for k, v in engine.vhead.state_dict().items())
        )

    def test_engine_head_only_checkpoint_uses_single_group_optimizer(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            # Simulate the production constructor's portable optimizer.
            engine.value_opt = torch.optim.AdamW(engine.vhead.parameters(), lr=1e-2)
            engine.value_head_path = Path(tmp) / "value_head.pt"
            result = engine.train_value(
                [{"prompt": "state", "value_target": 0.5}], epochs=1
            )
            self.assertEqual(result["examples"], 1)
            restored = ValueHead(4, hidden_dim=5)
            restored_opt = torch.optim.AdamW(restored.parameters(), lr=1e-2)
            metadata = load_value_head(engine.value_head_path, restored, restored_opt)
            self.assertTrue(metadata["optimizer_loaded"])
            self.assertEqual(metadata["optimizer_steps"], 1)

    def test_ttt_step_preserves_legacy_default_logprob(self) -> None:
        """The pre-value-head RTTT payload may omit ``logprob_old``."""

        engine = self._make_engine()
        result = engine.ttt_step(
            [{
                "prompt": "state",
                "target": "simp",
                "r": 0.0,
                "value_target": 0.2,
                # Deliberately omit logprob_old: the original endpoint used
                # -12.0 as its documented fallback.
            }]
        )
        self.assertEqual(result["steps"], 1)
        self.assertEqual(result["value_updates"], 1)

    def test_engine_snapshot_restore_includes_value_head_and_optimizer(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = self._make_engine(tmp)
            engine.ttt_step(
                [{
                    "prompt": "state",
                    "target": "simp",
                    "r": 0.0,
                    "logprob_old": 0.0,
                    "value_target": -0.6,
                }]
            )
            expected_model = {k: v.detach().clone() for k, v in engine.model.state_dict().items()}
            expected_head = {k: v.detach().clone() for k, v in engine.vhead.state_dict().items()}
            expected_steps = engine.value_optimizer_steps
            expected_examples = engine.value_examples_seen
            engine.snapshot("unit")

            payload = torch.load(Path(tmp) / "adapter_unit.pt", map_location="cpu", weights_only=True)
            self.assertEqual(payload["schema_version"], "reap.policy-server.snapshot.v2")
            self.assertIn("value_head", payload)
            self.assertIn("optimizer", payload)

            with torch.no_grad():
                for parameter in engine.model.parameters():
                    parameter.add_(1.0)
                for parameter in engine.vhead.parameters():
                    parameter.add_(1.0)
            engine.value_optimizer_steps = 99
            engine.value_examples_seen = 99

            self.assertEqual(engine.restore("unit"), "restored:unit")
            for key, value in expected_model.items():
                torch.testing.assert_close(engine.model.state_dict()[key], value)
            for key, value in expected_head.items():
                torch.testing.assert_close(engine.vhead.state_dict()[key], value)
            self.assertEqual(engine.value_optimizer_steps, expected_steps)
            self.assertEqual(engine.value_examples_seen, expected_examples)

    def test_value_endpoint_keeps_prompt_score_contract(self) -> None:
        module = self._import_policy_server()

        class _StubEngine:
            def value(self, prompt):
                self.prompt = prompt
                return 0.25

        module.ENGINE = _StubEngine()
        handler = module.H.__new__(module.H)
        handler.path = "/value"
        body = json.dumps({"prompt": "state"}).encode()
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        status = []
        handler.send_response = status.append
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None

        handler.do_POST()
        self.assertEqual(status, [200])
        payload = json.loads(handler.wfile.getvalue().decode())
        self.assertEqual(payload, {"score": 0.25})
        self.assertEqual(module.ENGINE.prompt, "state")

    def test_value_endpoint_accepts_state_alias_and_openai_value_envelope(self) -> None:
        module = self._import_policy_server()

        class _StubEngine:
            def value(self, prompt):
                self.prompt = prompt
                return -0.4

        module.ENGINE = _StubEngine()
        handler = module.H.__new__(module.H)
        handler.path = "/value/v1/chat/completions"
        body = json.dumps({"state": "legacy state", "model": "reap"}).encode()
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        status = []
        handler.send_response = status.append
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None

        handler.do_POST()
        self.assertEqual(status, [200])
        payload = json.loads(handler.wfile.getvalue().decode())
        self.assertEqual(module.ENGINE.prompt, "legacy state")
        self.assertEqual(payload["object"], "chat.completion")
        self.assertEqual(payload["model"], "reap")
        self.assertEqual(payload["choices"][0]["message"]["role"], "assistant")
        self.assertEqual(
            json.loads(payload["choices"][0]["message"]["content"]),
            {"score": -0.4},
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
