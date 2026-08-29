"""v2/eff_registry.py — Eff 通道白名单（spec 01）
DeterministicE：结果以独立可裁决检查（post-verifier）验证；
ExistentialE：默认禁用（禁止"实验噪声作为证据"）。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Any


class EffClass(str, Enum):
    DETERMINISTIC = "deterministic"
    EXISTENTIAL = "existential"


@dataclass
class EffSpec:
    name: str
    in_vals: List[int]
    verifier: str
    klass: EffClass = EffClass.DETERMINISTIC

    def to_json(self) -> dict:
        return {"name": self.name, "in_vals": self.in_vals,
                "verifier": self.verifier, "class": self.klass.value}


@dataclass
class EffObs:
    value: int
    ok: bool
    trace: str = ""


# 白名单效应（code-verified；名称即注册项的键）
_REGISTRY: Dict[str, Callable[[List[int]], int]] = {
    "sqsum-check": lambda vals: sum(v * v for v in vals),
    "arith-check": lambda vals: sum(vals),
}


def lookup(spec: EffSpec) -> EffObs:
    if spec.klass == EffClass.EXISTENTIAL:
        return EffObs(0, False, "existential effects disabled by default")
    fn = _REGISTRY.get(spec.verifier)
    if fn is None:
        return EffObs(0, False, f"unknown verifier: {spec.verifier}")
    try:
        v = fn(spec.in_vals)
        return EffObs(v, True, f"{spec.verifier}: ok")
    except Exception as e:
        return EffObs(0, False, f"effect error: {e}")


def public_verifiers() -> List[str]:
    return list(_REGISTRY.keys())
