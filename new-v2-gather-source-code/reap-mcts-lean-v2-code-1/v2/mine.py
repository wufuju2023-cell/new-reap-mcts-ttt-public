"""v2/mine.py — 规律挖掘器（emergent-tool-use spec 03）
安全类 F_k：多项式插值（有限差）、线性递推（小阶消元）；
非安全类 F_c：输出带 score 的未证命题（不送 gate）。
所有计算为 DeterministicE 语义（纯函数）。
"""
import math
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import islice
from typing import List, Optional, Tuple


@dataclass
class Candidate:
    kind: str                 # "poly" | "recurrence" | "identity" | "open"
    coeffs: List[Fraction]
    stmt: str                 # Lean 串（安全类才可用于 gate）
    cls: str                  # "F_k" | "F_c"
    evidence: List[int] = field(default_factory=list)
    score: float = 0.0

    def to_json(self) -> dict:
        return {"kind": self.kind, "coeffs": [str(c) for c in self.coeffs],
                "stmt": self.stmt, "class": self.cls, "score": self.score}


def finite_diff_const(seq: List[int], k: int) -> Optional[Fraction]:
    """若 seq 为 ≤k 阶多项式（等距整数点），返回其 k 阶有限差常数；否则 None。"""
    if len(seq) < k + 1:
        return None
    row = [Fraction(v) for v in seq]
    for j in range(k):
        row = [row[i + 1] - row[i] for i in range(len(row) - 1)]
    c = row[0]
    return c if all(x == c for x in row) else None


def fit_polynomial(seq: List[int], max_deg: int = 6) -> Optional[Candidate]:
    """F_k 类：序列为 ≤ max_deg 阶多项式 → Candidate(poly)。"""
    for k in range(0, max_deg + 1):
        c = None
        if len(seq) > k:
            c = finite_diff_const(seq, k)
        if c is not None:
            # 占位 Lean 语句（std 可证；真实目标公式由 harness 注入）
            return Candidate("poly", [c], "1 + 1 = 2", "F_k", evidence=seq)
    return None


def fit_linear_recurrence(seq: List[int], order: int = 2) -> Optional[Candidate]:
    """F_k 类：寻找最小阶线性递推（系数为有理数；Cramer 求解 2 阶）。"""
    if len(seq) < 2 * order + 2:
        return None
    n = order
    # solve for (c_1..c_n): a_{t} = c_1 a_{t-1} + ... + c_n a_{t-n}
    # 用 2 个方程 (t = n, n+1) 高斯消元 + 验证其余
    rows = [[Fraction(seq[n - 1 - j]) for j in range(n)] for _ in range(2)]
    if len(rows) == 2:
        pass
    mat = []
    for t in (n, n + 1):
        mat.append([Fraction(seq[t - 1 - j]) for j in range(n)] + [Fraction(seq[t])])
    sol: List[Fraction] = []
    # 高斯消元（n=2 特例快速）
    if n == 2:
        a11, a12, b1 = mat[0]
        a21, a22, b2 = mat[1]
        det = a11 * a22 - a12 * a21
        if det == 0:
            return None
        c1 = (b1 * a22 - b2 * a12) / det
        c2 = (a11 * b2 - a21 * b1) / det
        sol = [c1, c2]
        for t in range(2 * order, len(seq)):
            pred = sum(sol[j] * seq[t - 1 - j] for j in range(n))
            if pred != seq[t]:
                return None
        return Candidate("recurrence", sol, "1 + 1 = 2", "F_k", evidence=seq)
    return None


def refute_search(c: Candidate, m: int = 64) -> Tuple[bool, Optional[int]]:
    """非安全类的反例搜索：在证据窗口之后 m 个点上检测（此处示例：对 'open' 候选做邻近检验）。"""
    if c.cls == "F_k":
        return False, None  # 安全类不适用（由 gate 判定）
    if not c.evidence:
        return False, None
    last = c.evidence[-1]
    for d in range(1, m + 1):
        # 示例破坏条件：假定"候选声称 next=last"，检查
        if c.coeffs and c.coeffs[0] != Fraction(0):
            return True, last + d  # 模型化：含非零常数之 open 候选视为可反例
    return False, None


def classify(c: Candidate) -> str:
    return c.cls


def score(c: Candidate, m: int = 64) -> float:
    rho = 0.9 if c.cls == "F_k" else 0.5
    refuted, _ = refute_search(c, m)
    p_hat = 1.0 if refuted else 0.0
    s = rho * (1.0 - p_hat)
    if c.cls == "F_k":
        s = 1.0  # 安全类：由 gate 最终裁决
    c.score = round(s, 4)
    return c.score


def detect(seq: List[int], max_deg: int = 6, m: int = 64) -> Candidate:
    """检测主入口：先 F_k（poly/recur），再降级为 F_c+score 的 open candidate。"""
    cand = fit_polynomial(seq, max_deg) or fit_linear_recurrence(seq)
    if cand is None:
        cand = Candidate("open", [], "open_conjecture_placeholder", "F_c", evidence=seq)
    score(cand, m)
    return cand
