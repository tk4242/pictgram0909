"""学習ループ（予測 vs 実績のキャリブレーション）.

他AI案 §15 は「予測95% → 実績が失敗 → 70% に補正」としているが、これは
1サンプルでの上書きであり過学習になる。本実装はベータ・ベイズ更新を採用し、
シミュレータ上で両者の推定誤差を比較できるようにしてある（run.py --learn）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BetaEstimator:
    """承認確率の推定. 事前分布 Beta(a0, b0)."""
    a0: float = 2.0
    b0: float = 1.0
    stats: dict[tuple[str, str], list[int]] = field(default_factory=dict)

    def key(self, site: str, category: str) -> tuple[str, str]:
        return (site, category)

    def prior(self, site: str, category: str) -> float:
        a, b = self.stats.get(self.key(site, category), [0, 0])
        return (a + self.a0) / (a + b + self.a0 + self.b0)

    def update(self, site: str, category: str, success: bool) -> None:
        k = self.key(site, category)
        rec = self.stats.setdefault(k, [0, 0])
        rec[0 if success else 1] += 1

    def samples(self, site: str, category: str) -> int:
        a, b = self.stats.get(self.key(site, category), [0, 0])
        return a + b


@dataclass
class NaiveEstimator:
    """比較対象: 直近1件の結果で値を大きく書き換える方式."""
    values: dict[tuple[str, str], float] = field(default_factory=dict)
    default: float = 0.90

    def prior(self, site: str, category: str) -> float:
        return self.values.get((site, category), self.default)

    def update(self, site: str, category: str, success: bool) -> None:
        cur = self.prior(site, category)
        self.values[(site, category)] = min(0.99, cur + 0.05) if success else max(0.05, cur - 0.25)


@dataclass
class ModelScorecard:
    """どのモデルがどのカテゴリで強いかを記録する（他AI案 §19 の model_predictions）."""
    hits: dict[tuple[str, str], list[int]] = field(default_factory=dict)

    def record(self, model: str, category: str, correct: bool) -> None:
        rec = self.hits.setdefault((model, category), [0, 0])
        rec[0 if correct else 1] += 1

    def accuracy(self, model: str, category: str) -> float | None:
        rec = self.hits.get((model, category))
        if not rec or sum(rec) == 0:
            return None
        return rec[0] / sum(rec)

    def by_model(self) -> dict[str, float]:
        agg: dict[str, list[int]] = {}
        for (model, _cat), rec in self.hits.items():
            a = agg.setdefault(model, [0, 0])
            a[0] += rec[0]
            a[1] += rec[1]
        return {m: (v[0] / sum(v) if sum(v) else 0.0) for m, v in agg.items()}
