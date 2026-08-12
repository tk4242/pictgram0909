"""継続課金案件（初月無料・以降有料）の解約忘れリスクを定量化する.

問い: 「初月無料、継続で有料」の案件は解約を忘れるリスクがないか?
答え: ある。しかも報酬より損失の方が大きくなりうる。

このモジュールは4つの管理方式を比較し、どこまで対策すれば
「報酬 > 漏れた課金」になるかを実測する。

モデルの仮定（すべて調整可能。実運用の実績で置き換えること）:
  - 解約を忘れる確率は「同時に抱えている未解約案件数」で悪化する
    （通知の有無より、仕掛かり件数の方が効く）
  - 忘れた場合、気づくまでの月数は幾何分布（平均4ヶ月）
  - 通知はエスカレーションするほど効くが、WIP が多いと効果が飽和する
"""
from __future__ import annotations

import random
from dataclasses import dataclass

# 忘れる基礎確率（WIP=1 のとき）
BASE_FORGET = {
    "manual": 0.25,        # 管理なし。カレンダーに手で入れる程度
    "single": 0.12,        # 期限3日前に1回だけ通知
    "escalate": 0.05,      # 30日前/7日前/3日前/前日/当日の多段通知
    "escalate_wip": 0.05,  # 多段通知 + WIP制限
}

# 同時に抱える未解約案件が1件増えるごとに、忘れる確率が何倍になるか
WIP_PENALTY = 1.45

# 忘れたあと、気づくまでの月数（幾何分布のパラメータ）
NOTICE_P = 0.25

WIP_LIMIT = 2   # escalate_wip 方式での同時保有上限


@dataclass
class TrialOffer:
    reward_yen: float      # 案件報酬
    monthly_fee: float     # 解約し損ねた場合の月額
    free_days: int


def make_offers(rng: random.Random, n: int) -> list[TrialOffer]:
    out = []
    for _ in range(n):
        out.append(TrialOffer(
            reward_yen=float(rng.randint(800, 4000)),
            monthly_fee=float(rng.choice([500, 980, 1480, 1980, 2980])),
            free_days=rng.choice([14, 30, 31]),
        ))
    return out


def forget_probability(policy: str, wip: int) -> float:
    p = BASE_FORGET[policy] * (WIP_PENALTY ** max(0, wip - 1))
    return min(0.95, p)


def simulate(rng: random.Random, offers: list[TrialOffer], policy: str) -> dict:
    """月次の時間軸で処理する.

    1ヶ月に1件ずつ案件が来る。解約し損ねた案件は「気づくまで」課金され続け、
    その間ずっと WIP を占有する ——ここが本質。
    放置中の案件が多いほど、次の案件も落としやすくなる悪循環が生まれる。
    """
    reward = leaked = 0.0
    forgot = declined = 0
    # 解約し損ねて放置中の案件: [月額, 残り月数] のリスト
    leaking: list[float] = []

    for off in offers:
        # --- 今月の課金漏れを計上し、気づいたものは解約する ---
        still = []
        for fee in leaking:
            leaked += fee
            if rng.random() >= NOTICE_P:      # まだ気づかない
                still.append(fee)
        leaking = still

        # --- WIP = 放置中の件数 + これから抱える1件 ---
        wip = len(leaking) + 1

        # WIP 制限方式は、放置中が上限に達している間は新規案件を取らない
        if policy == "escalate_wip" and len(leaking) >= WIP_LIMIT:
            declined += 1
            continue

        reward += off.reward_yen
        if rng.random() < forget_probability(policy, wip):
            forgot += 1
            leaking.append(off.monthly_fee)

    # 観測期間の終わりに残っている漏れは、あと平均 1/NOTICE_P ヶ月続く
    for fee in leaking:
        leaked += fee / NOTICE_P

    taken = len(offers) - declined
    return {
        "policy": policy,
        "taken": taken,
        "declined": declined,
        "reward": reward,
        "leaked": leaked,
        "net": reward - leaked,
        "forgot": forgot,
        "forget_rate": forgot / max(taken, 1),
    }


def run(seed: int = 20260812, n_offers: int = 48, trials: int = 400) -> None:
    """48件（4年ぶん相当）の無料体験案件を、4方式で繰り返し処理して比較する."""
    print("=" * 78)
    print(f" 継続課金案件の解約忘れシミュレーション（{n_offers}件 × {trials}試行の平均）")
    print("=" * 78)
    print(f"{'管理方式':<28}{'着手':>5}{'報酬':>11}{'漏れた課金':>12}{'純利益':>11}{'忘れ率':>8}")
    print("-" * 78)

    labels = {
        "manual": "① 管理なし（手動）",
        "single": "② 期限3日前に1回通知",
        "escalate": "③ 多段エスカレーション通知",
        "escalate_wip": "④ ③ + WIP制限（同時2件）",
    }

    results = {}
    for policy in ("manual", "single", "escalate", "escalate_wip"):
        agg = {"taken": 0, "reward": 0.0, "leaked": 0.0, "net": 0.0,
               "forgot": 0, "declined": 0}
        for t in range(trials):
            rng = random.Random(seed + t)
            offers = make_offers(rng, n_offers)
            r = simulate(random.Random(seed + t * 7919), offers, policy)
            for k in agg:
                agg[k] += r[k]
        for k in agg:
            agg[k] /= trials
        results[policy] = agg
        print(f"{labels[policy]:<28}{agg['taken']:>5.0f}"
              f"{agg['reward']:>11,.0f}{agg['leaked']:>12,.0f}"
              f"{agg['net']:>11,.0f}"
              f"{agg['forgot'] / max(agg['taken'], 1):>8.1%}")

    print("-" * 78)
    m, w = results["manual"], results["escalate_wip"]
    print(f"\n  管理なしでは、報酬 ¥{m['reward']:,.0f} に対して漏れた課金が "
          f"¥{m['leaked']:,.0f}（報酬の {m['leaked'] / m['reward']:.0%}）。")
    if m["net"] < 0:
        print(f"  → 純利益 ¥{m['net']:,.0f} で、やればやるほど損をする領域に入っている。")

    e = results["escalate"]
    print(f"\n  多段通知の効果（①→③）      : 純利益 ¥{m['net']:,.0f} → ¥{e['net']:,.0f}  ← 主効果はここ")
    print(f"  WIP制限を足した効果（③→④）: 純利益 ¥{e['net']:,.0f} → ¥{w['net']:,.0f}  ← 平時はほぼ効かない")

    # --- ストレス条件: 通知が効かなくなった場合 ---
    print("\n" + "=" * 78)
    print(" ストレス条件: 通知疲れで多段通知が効かなくなった場合（忘れ率 5% → 18%）")
    print("=" * 78)
    saved = BASE_FORGET["escalate"], BASE_FORGET["escalate_wip"]
    BASE_FORGET["escalate"] = BASE_FORGET["escalate_wip"] = 0.18
    stress = {}
    for policy in ("escalate", "escalate_wip"):
        agg = {"taken": 0, "reward": 0.0, "leaked": 0.0, "net": 0.0,
               "forgot": 0, "declined": 0}
        for t in range(trials):
            offers = make_offers(random.Random(seed + t), n_offers)
            r = simulate(random.Random(seed + t * 7919), offers, policy)
            for k in agg:
                agg[k] += r[k]
        for k in agg:
            agg[k] /= trials
        stress[policy] = agg
        print(f"{labels[policy]:<28}{agg['taken']:>5.0f}"
              f"{agg['reward']:>11,.0f}{agg['leaked']:>12,.0f}"
              f"{agg['net']:>11,.0f}"
              f"{agg['forgot'] / max(agg['taken'], 1):>8.1%}")
    BASE_FORGET["escalate"], BASE_FORGET["escalate_wip"] = saved

    se, sw = stress["escalate"], stress["escalate_wip"]
    print("-" * 78)
    print(f"\n  通知が劣化すると WIP制限なしは ¥{se['net']:,.0f}、ありは ¥{sw['net']:,.0f}。")
    print(f"  差は ¥{sw['net'] - se['net']:,.0f}。着手を {se['taken']:.0f}件 → {sw['taken']:.0f}件 "
          f"に絞ってなお勝つ。")

    print("\n【結論】")
    print("  1. 主効果は多段エスカレーション通知。これだけで赤字→黒字に反転する。")
    print("  2. WIP制限は平時ほぼ効かない。効くのは通知が劣化したときだけ。")
    print("     つまり利益を増やす装置ではなく、破綻を防ぐサーキットブレーカー。")
    print("  3. 管理手段が無いなら、この案件カテゴリには着手しない方が儲かる。")


if __name__ == "__main__":
    run()
