"""v2/tower.py — 塔上升（spec 03）：库 L + gate。
gate 是外部 kernel 校验（回调）；register 仅当 gate ok；抽象深度/塔高单调。
"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Callable, List, Optional
from pathlib import Path


@dataclass
class TowerEntry:
    name: str
    body: str
    deps: List[str] = field(default_factory=list)
    type: str = "1 + 1 = 2"      # gate_lean 验证的目标语句（标准库命题）


@dataclass
class Tower:
    lib: List[TowerEntry] = field(default_factory=list)

    def register(self, e: TowerEntry, gate_ok: bool) -> bool:
        if not gate_ok:
            return False
        self.lib.append(e)
        return True

    def depth(self, e: TowerEntry) -> int:
        names = {t.name for t in self.lib}
        return sum(1 for d in e.deps if d in names)
    def height(self) -> int:
        return max([self.depth(e) for e in self.lib], default=0)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"lib": [asdict(e) for e in self.lib]}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "Tower":
        if not os.path.exists(path):
            return Tower()
        with open(path) as f:
            d = json.load(f)
        return Tower(lib=[TowerEntry(**e) for e in d.get("lib", [])])


# gate 回调签名: Callable[[TowerEntry], bool]；实现侧 = lean kernel checkProof
GateFn = Callable[[TowerEntry], bool]
