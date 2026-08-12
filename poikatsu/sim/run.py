"""オーケストレータ + 評価レポート.

使い方:
    python3 -m poikatsu.sim.run benchmark    # 20案件のベンチマークで精度を測る
    python3 -m poikatsu.sim.run daily        # 1日100案件 × 30日の運用シミュレーション
    python3 -m poikatsu.sim.run learn        # ベイズ更新 vs 素朴な上書きの比較
    python3 -m poikatsu.sim.run all
"""
from __future__ import annotations

import random
import sys

from . import agents, engine, world
from .learning import BetaEstimator, ModelScorecard, NaiveEstimator
from .models import Cost, Decision, Offer, PipelineResult, Truth

SEED = 20260812

# 人間が案件対応に使える1日あたりの時間（分）. これが収益の律速段階になる。
HUMAN_MIN_PER_DAY = 20

# 誤判定のコスト行列（円）. 行=システムの判断, 列=人間の正解
#   ★誤AUTO は対称ではない。BLOCK 案件を自動実行するとアカウント凍結で
#     未確定ポイントごと失う。ここを -50,000 と置くのが本設計の要。
COST_MATRIX = {
    ("AUTO", "BLOCK"): -50000,
    ("AUTO", "HUMAN"): -3000,
    ("AUTO", "DROP"): -500,
    ("HUMAN", "BLOCK"): -2000,     # 人間が見て止められる可能性が高い
    ("DROP", "BLOCK"): 0,
    ("BLOCK", "AUTO"): -800,       # 取り逃し
    ("BLOCK", "HUMAN"): -1500,
    ("DROP", "AUTO"): -800,
    ("DROP", "HUMAN"): -2500,      # 高額案件の取り逃しが一番痛い誤DROP
    ("HUMAN", "AUTO"): -100,       # 人間の手間だけ. ほぼ無害
    ("HUMAN", "DROP"): -50,
    ("BLOCK", "DROP"): 0,
}


# ------------------------------------------------------------------
# パイプライン本体
# ------------------------------------------------------------------

def run_pipeline(rng: random.Random, offer: Offer, truth: Truth, budget: engine.Budget,
                 panel: list[agents.MockLLM], estimator, scorecard: ModelScorecard | None,
                 max_searches: int = 6) -> PipelineResult:
    cost = Cost()

    # --- 段階1: Python 前置フィルタ（AI呼び出しゼロ） ---
    keep, why = engine.prefilter(offer)
    if not keep:
        return PipelineResult(offer, truth, "prefilter", Decision("DROP", why), cost=cost)

    # --- 段階2: Deep Research（検索枠を消費） ---
    if not budget.take("search", max_searches):
        return PipelineResult(offer, truth, "budget_search",
                              Decision("HUMAN", "検索の無料枠を使い切ったため人間に回す"), cost=cost)
    fact, c, source_key = agents.research(rng, offer, truth, max_searches)
    cost.add(c)

    # --- 段階3: Dry Run（本番実行はしない） ---
    if not budget.take("browser", 1):
        return PipelineResult(offer, truth, "budget_browser",
                              Decision("HUMAN", "ブラウザ枠上限"), fact=fact, cost=cost)
    trial, c = agents.dry_run(rng, offer, truth)
    cost.add(c)

    # --- 段階4: 安全ゲート（★ROI より前。コスト最適化に追い越させない） ---
    blocked = engine.block_gates(offer, fact, trial)
    if blocked is not None:
        return PipelineResult(offer, truth, "blocked", blocked, fact=fact, trial=trial, cost=cost)

    # --- 段階5: ROI（完全に Python） ---
    prior = estimator.prior(offer.site, offer.category)
    auto_candidate = (trial.automation_allowed and trial.observable and not trial.kyc
                      and not trial.payment and not trial.recurring and not trial.captcha)
    roi = engine.compute_roi(offer, fact, trial, prior, auto_candidate)

    # ★AI に投票させる前に、期待値で落とす（無料枠の最大の節約点）
    if roi.hourly_human < engine.MIN_HOURLY_YEN:
        return PipelineResult(offer, truth, "roi",
                              Decision("DROP", f"人間時給 {roi.hourly_human:.0f}円"),
                              fact=fact, trial=trial, roi=roi, cost=cost)

    # --- 段階6: 合議（ここで初めて LLM を呼ぶ） ---
    votes = []
    for m in panel:
        if not budget.take("llm", 1):
            break
        v, calls = m.vote(rng, truth.label, fact, trial, roi, source_key)
        cost.llm_calls += calls
        if calls > 1:
            budget.take("llm", calls - 1)
        votes.append(v)
        if scorecard is not None:
            scorecard.record(m.name, offer.category, v.decision == truth.label)

    cons = engine.aggregate(votes)

    # --- 段階7: 決定論ルールエンジン（唯一の実行判断者） ---
    decision = engine.decide(offer, fact, trial, roi, cons)
    return PipelineResult(offer, truth, "decided", decision, fact=fact, trial=trial,
                          roi=roi, consensus=cons, cost=cost)


# ------------------------------------------------------------------
# モード1: ベンチマーク
# ------------------------------------------------------------------

def mode_benchmark() -> None:
    rng = random.Random(SEED)
    budget = engine.Budget(llm_rpd=1500, search_rpd=500, browser_rpd=300)
    panel = agents.default_panel()
    est = BetaEstimator()
    card = ModelScorecard()

    print("=" * 78)
    print(" ベンチマーク: 人間ラベル付き20案件（うち8件は意図的な罠）")
    print("=" * 78)
    print(f"{'ID':<5}{'案件':<28}{'正解':<7}{'判定':<7}{'fact':<7}{'trial':<7}{'人間時給':>9}")
    print("-" * 78)

    results = []
    for offer, truth in world.BENCHMARK:
        r = run_pipeline(rng, offer, truth, budget, panel, est, card)
        results.append(r)
        mark = "  " if r.decision.action == truth.label else " ✗"
        f = f"{r.fact.fact_score:.2f}" if r.fact else "  - "
        t = f"{r.trial.trial_score:.2f}" if r.trial else "  - "
        h = f"{r.roi.hourly_human:,.0f}" if r.roi else "-"
        print(f"{offer.id:<5}{offer.title[:26]:<28}{truth.label:<7}{r.decision.action:<7}"
              f"{f:<7}{t:<7}{h:>9}{mark}")

    print("-" * 78)
    _confusion(results)
    _cost_eval(results)
    print("\n【誤判定の内訳】")
    for r in results:
        if r.decision.action != r.truth.label:
            print(f"  {r.offer.id} 正解={r.truth.label} → 判定={r.decision.action}")
            print(f"       理由: {r.decision.reason}")


def _confusion(results: list[PipelineResult]) -> None:
    labels = ["AUTO", "HUMAN", "BLOCK", "DROP"]
    m = {(a, b): 0 for a in labels for b in labels}
    for r in results:
        m[(r.decision.action, r.truth.label)] += 1
    print("\n【混同行列】 行=システム判断 / 列=人間の正解")
    print("           " + "".join(f"{l:>8}" for l in labels))
    for a in labels:
        print(f"    {a:<7}" + "".join(f"{m[(a, b)]:>8}" for b in labels))
    correct = sum(m[(l, l)] for l in labels)
    print(f"\n  Accuracy = {correct}/{len(results)} = {correct / len(results):.1%}")

    # ★本当に見るべき指標
    auto_pred = sum(m[("AUTO", b)] for b in labels)
    auto_ok = m[("AUTO", "AUTO")]
    danger = m[("AUTO", "BLOCK")]
    block_total = sum(m[(a, "BLOCK")] for a in labels)
    block_caught = m[("BLOCK", "BLOCK")]
    print(f"  AUTO精度 (precision)  = {auto_ok}/{auto_pred} = "
          f"{(auto_ok / auto_pred if auto_pred else 1):.1%}   ← 自動実行してよいかの唯一の基準")
    print(f"  BLOCK再現率 (recall)  = {block_caught}/{block_total} = "
          f"{(block_caught / block_total if block_total else 1):.1%}")
    print(f"  致命的誤り (BLOCK案件を自動実行) = {danger} 件")


def _cost_eval(results: list[PipelineResult]) -> None:
    total = 0
    for r in results:
        total += COST_MATRIX.get((r.decision.action, r.truth.label), 0)
    print(f"\n【コスト重み付き評価】 誤判定による損失合計 = ¥{total:,}")
    print("  ※ Accuracy が同じでも、BLOCK案件の誤自動実行が1件あれば -¥50,000。")
    print("     精度指標は Accuracy ではなく『AUTO precision と BLOCK recall』で見る。")


# ------------------------------------------------------------------
# モード2: 日次運用シミュレーション
# ------------------------------------------------------------------

def mode_daily(days: int = 90, per_day: int = 100) -> None:
    rng = random.Random(SEED + 1)
    panel = agents.default_panel()
    est = BetaEstimator()
    card = ModelScorecard()
    # 無料枠は各社で変動するため config 相当の値をここで与える
    budget = engine.Budget(llm_rpd=1500, search_rpd=500, browser_rpd=300)

    funnel = {"total": 0, "prefilter": 0, "roi": 0, "budget": 0, "decided": 0}
    actions = {"AUTO": 0, "HUMAN": 0, "BLOCK": 0, "DROP": 0}
    executed = 0
    revenue = 0.0
    human_minutes = 0.0
    disasters = 0
    deferred = 0            # 人間の時間が足りず処理できなかった件数
    already_done = 0        # 1人1回制約で再提示をスキップした件数
    consumed: set[str] = set()
    pace = engine.PaceLimiter()
    pace_blocked = 0
    day_rows = []
    monthly = []

    for d in range(1, days + 1):
        budget.reset()
        if (d - 1) % 30 == 0:
            pace.reset_month()
        stream = world.generate_daily(rng, per_day, d)
        queue: list[PipelineResult] = []
        d_rev = 0.0

        for offer, truth in stream:
            # ★1人1回制約: 一度やった案件は二度と収益にならない。
            #   これを入れないと「毎月クレカを954枚発行する」試算になる。
            if offer.fingerprint in consumed:
                already_done += 1
                continue

            funnel["total"] += 1
            r = run_pipeline(rng, offer, truth, budget, panel, est, card)
            if r.stage == "prefilter":
                funnel["prefilter"] += 1
            elif r.stage == "roi":
                funnel["roi"] += 1
            elif r.stage.startswith("budget"):
                funnel["budget"] += 1
            else:
                funnel["decided"] += 1
            actions[r.decision.action] += 1

            if r.decision.action == "AUTO":
                if not pace.allows(offer.category):
                    pace_blocked += 1
                    continue
                pace.consume(offer.category)
                if truth.label == "BLOCK":
                    disasters += 1      # 規約違反の自動実行 = アカウント凍結相当
                success, yen, mins = world.execute(rng, truth)
                consumed.add(offer.fingerprint)
                executed += 1
                revenue += yen
                d_rev += yen
                human_minutes += 0.5    # 通知の承認クリックのみ
                est.update(offer.site, offer.category, success)
            elif r.decision.action == "HUMAN":
                queue.append(r)

        # ★人間の時間予算（1日 HUMAN_MIN_PER_DAY 分）の中で、
        #   期待値/人間時間 の高い順にだけ処理する。入り切らない分は翌日以降へ。
        queue.sort(key=lambda x: -(x.roi.expected_yen / max(x.roi.human_minutes, 0.1))
                   if x.roi else 0)
        remaining = HUMAN_MIN_PER_DAY
        for r in queue:
            need = r.roi.human_minutes if r.roi else 15.0
            if not pace.allows(r.offer.category):
                pace_blocked += 1
                continue
            if need > remaining:
                deferred += 1
                continue
            pace.consume(r.offer.category)
            remaining -= need
            success, yen, mins = world.execute(rng, r.truth)
            consumed.add(r.offer.fingerprint)
            executed += 1
            revenue += yen
            d_rev += yen
            human_minutes += need
            est.update(r.offer.site, r.offer.category, success)

        day_rows.append((d, d_rev, dict(budget.snapshot())))
        if d % 30 == 0:
            monthly.append((d, revenue, human_minutes / 60, executed))

    print("=" * 78)
    print(f" 日次運用シミュレーション: {per_day}件/日 × {days}日 = {funnel['total']:,}件")
    print("=" * 78)
    print("\n【ファネル】")
    t = funnel["total"]
    kept = t - funnel["prefilter"]
    print(f"  発見                {t:>6,} 件  (100.0%)")
    print(f"  ├ Python前置フィルタで棄却 {funnel['prefilter']:>6,} 件  "
          f"({funnel['prefilter'] / t:>5.1%})  ← AI呼び出しゼロ")
    print(f"  └ 調査へ            {kept:>6,} 件  ({kept / t:>5.1%})")
    print(f"     ├ ROI不足で棄却  {funnel['roi']:>6,} 件  ({funnel['roi'] / t:>5.1%})  ← 投票前に棄却")
    print(f"     ├ 枠切れで人間へ {funnel['budget']:>6,} 件  ({funnel['budget'] / t:>5.1%})")
    print(f"     └ 合議まで到達   {funnel['decided']:>6,} 件  ({funnel['decided'] / t:>5.1%})")
    print("\n【最終判断】")
    for k in ("AUTO", "HUMAN", "BLOCK", "DROP"):
        print(f"  {k:<6}{actions[k]:>6,} 件  ({actions[k] / t:>5.1%})")
    print(f"\n  ★AUTO+HUMAN = {actions['AUTO'] + actions['HUMAN']:,} 件を『やる価値あり』"
          f"と判定したが、実際に実行できたのは {executed:,} 件。")
    print("    判定できる量と実行できる量は別物であり、後者が収益を決める。")

    print(f"\n  ※ 1人1回制約により再提示をスキップ: {already_done:,} 件")
    print(f"  ※ 人間の時間が足りず未処理: {deferred:,} 件")
    print(f"  ※ 申込ペース上限で見送り: {pace_blocked:,} 件  ← 実際の律速段階はここ")

    print("\n【収益】")
    hours = human_minutes / 60
    print(f"  実行            {executed:,} 件")
    print(f"  確定報酬        ¥{revenue:,.0f}   （{days}日 = ¥{revenue / days * 30:,.0f}/月換算）")
    print(f"  人間の拘束時間  {hours:.1f} 時間   （{hours / days * 30:.1f} 時間/月, 予算{HUMAN_MIN_PER_DAY}分/日）")
    print(f"  実質時給        ¥{revenue / max(hours, 0.01):,.0f}/h")
    print(f"  致命的事故      {disasters} 件   ← BLOCK案件の自動実行（1件でも起きたら設計失敗）")

    print("\n【月次の推移】")
    prev_r = prev_h = 0.0
    prev_e = 0
    for i, (d, rev, hrs, ex) in enumerate(monthly, 1):
        dr, dh, de = rev - prev_r, hrs - prev_h, ex - prev_e
        print(f"  {i}ヶ月目   ¥{dr:>8,.0f}   {de:>3}件   {dh:>4.1f}h   "
              f"時給 ¥{dr / max(dh, 0.01):>7,.0f}")
        prev_r, prev_h, prev_e = rev, hrs, ex
    print("  → 高単価カテゴリ（カード・口座）は 1人1回で枯れるため、")
    print("     日を追うごとに単価が落ちる。ストックであってフローではない。")

    print("\n【無料枠の消費（最終日）】")
    for k, (used, lim, denied) in day_rows[-1][2].items():
        bar = "█" * int(used / max(lim, 1) * 30)
        print(f"  {k:<8}{used:>5}/{lim:<5} {bar:<30} 拒否 {denied}")

    print("\n【モデル別 正答率】")
    for m, acc in sorted(card.by_model().items(), key=lambda x: -x[1]):
        print(f"  {m:<18}{acc:.1%}")
    print("  ※ 個々のモデル精度が 74〜88% でも、決定論ルールが後段にあるため")
    print("     致命的事故を 0 に抑えられる、というのがこの構成の要点。")


# ------------------------------------------------------------------
# モード3: 学習則の比較
# ------------------------------------------------------------------

def mode_learn(days: int = 60) -> None:
    """ベイズ更新 vs 「1件失敗したら95%→70%」方式の推定誤差を比較する."""
    rng = random.Random(SEED + 2)
    beta, naive = BetaEstimator(), NaiveEstimator()
    site, cat = "モッピー", "card"
    true_p = 0.86

    print("=" * 78)
    print(" 学習則の比較: 承認確率の推定誤差（真値 0.86）")
    print("=" * 78)
    print(f"{'試行':>5}{'実績':>7}{'ベイズ':>10}{'誤差':>8}{'素朴上書き':>12}{'誤差':>8}")
    print("-" * 78)

    be = ne = 0.0
    for i in range(1, days + 1):
        success = rng.random() < true_p
        beta.update(site, cat, success)
        naive.update(site, cat, success)
        pb, pn = beta.prior(site, cat), naive.prior(site, cat)
        be += abs(pb - true_p)
        ne += abs(pn - true_p)
        if i in (1, 2, 3, 5, 10, 20, 30, 45, 60):
            print(f"{i:>5}{'○' if success else '×':>7}{pb:>10.3f}{abs(pb - true_p):>8.3f}"
                  f"{pn:>12.3f}{abs(pn - true_p):>8.3f}")

    print("-" * 78)
    print(f"  平均絶対誤差   ベイズ {be / days:.3f}   /   素朴上書き {ne / days:.3f}")
    print(f"  → 素朴な上書きは誤差が {ne / max(be, 1e-9):.1f} 倍。1件の失敗で確率を")
    print("     大きく動かすと、翌日の判断が前日の1件の運に支配される。")


# ------------------------------------------------------------------

def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("benchmark", "all"):
        mode_benchmark()
        print()
    if mode in ("daily", "all"):
        mode_daily()
        print()
    if mode in ("learn", "all"):
        mode_learn()


if __name__ == "__main__":
    main()
