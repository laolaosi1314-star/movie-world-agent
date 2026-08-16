"""模拟工具：确定性、有界的噪声函数。

设计约束（防随机生成导致世界失真）：
  - 所有"意外"都来自确定性函数（seed + 实体 id 可复现），而非 random()。
  - 噪声幅度被严格限制（默认 ±8%），且必须记为因子/事件，绝不主导结果。
"""
import hashlib


def deterministic_unit(a: int, b: int, seed: int = 0) -> float:
    """返回 [0,1) 之间的确定性值，输入相同则输出相同。"""
    payload = f"{a}:{b}:{seed}".encode("utf-8")
    digest = hashlib.md5(payload).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def bounded_noise(a: int, b: int, seed: int = 0, amplitude: float = 0.08) -> float:
    """返回 [-amplitude, +amplitude] 的有界噪声。"""
    u = deterministic_unit(a, b, seed)
    return (u * 2 - 1) * amplitude


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def weighted_avg(pairs, default=50.0):
    """pairs: [(value, weight), ...]；返回加权均值，空则 default。"""
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        return default
    return sum(v * w for v, w in pairs) / total_w
