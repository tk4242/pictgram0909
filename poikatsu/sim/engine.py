"""決定論パート（Python が担当する領域）.

設計の核心:
    LLM は「判断材料」を作るだけ。金額計算と最終決定は必ずここを通る。
    LLM の出力がどれだけ自信満々でも、このルールを迂回する経路は存在しない。
"""
from __future__ import annotations

from typing import Optional

from .models import (Consensus, Cost, Decision, Evidence, FactReport, Offer,
                     RoiReport, TrialReport, Vote)

# ------------------------------------------------------------------
# 無料枠バジェット
# ------------------------------------------------------------------


class Budget:
    """無料枠の消費を管理する.

    RPD の実値は各社で頻繁に変わるため、必ず config から与える。
    コード内に定数として埋め込まない（陳腐化した数値で自動判断させないため）。
    """

    def __init__(self, llm_rpd: int, search_rpd: int, browser_rpd: int):
        self.limits = {"llm": llm_rpd, "search": search_rpd, "browser": browser_rpd}
        self.used = {"llm": 0, "search": 0, "browser": 0}
        self.denied = {"llm": 0, "search": 0, "browser": 0}

    def take(self, kind: str, n: int = 1) -> bool:
        if self.used[kind] + n > self.limits[kind]:
            self.denied[kind] += n
            return False
        self.used[kind] += n
        return True

    def reset(self) -> None:
        for k in self.used:
            self.used[k] = 0

    def snapshot(self) -> dict:
        return {k: (self.used[k], self.limits[k], self.denied[k]) for k in self.used}


# ------------------------------------------------------------------
# 申込ペース制御
# ------------------------------------------------------------------

# ★シミュレーションで発覚した最重要の欠落制約。
#   期待値だけで並べると「1ヶ月でクレカ40枚発行」という解が出る。
#   現実には多重申込は審査落ちを招き、信用情報にも記録が残る。
#   収益機会の総量ではなく、この月次上限が実際の収益天井を決める。
PACE_LIMIT_PER_MONTH = {
    "card": 2,          # 多重申込は審査落ち・信用情報に影響
    "bank": 3,
    "securities": 3,
    "fx": 1,            # 実費が大きく資金拘束も伴う
    "trial": 4,         # 解約管理の限界
    # ★ショッピング案件は「買い物をした人だけが得られる報酬」であって、
    #   案件が存在する数だけ実行できるものではない。上限は自分の購買回数。
    #   ここを無制限にすると『1日20件の買い物経由』という非現実解が出る
    #   （シミュレーションで月¥350,000 という過大な数字が出た原因）。
    "shopping": 15,     # 月間のネット購買回数
    "survey": 999,      # 実行はするが自動化は BLOCK 側で止まる
    "app": 999,
}


class PaceLimiter:
    """カテゴリ別の月次申込上限を管理する."""

    def __init__(self, limits: dict[str, int] | None = None):
        self.limits = limits or PACE_LIMIT_PER_MONTH
        self.count: dict[str, int] = {}

    def allows(self, category: str) -> bool:
        return self.count.get(category, 0) < self.limits.get(category, 999)

    def consume(self, category: str) -> None:
        self.count[category] = self.count.get(category, 0) + 1

    def reset_month(self) -> None:
        self.count.clear()


# ------------------------------------------------------------------
# 段階1: Python 前置フィルタ（AI を呼ぶ前に落とす）
# ------------------------------------------------------------------

MIN_REWARD_YEN = 100.0
MIN_HOURLY_YEN = 1500.0
MIN_DEADLINE_DAYS = 2


def prefilter(offer: Offer) -> tuple[bool, str]:
    """AI を1回も呼ばずに判定できるものを落とす.

    ここで落とせた割合が、そのまま無料枠の余裕になる。
    """
    if offer.deadline_days < MIN_DEADLINE_DAYS:
        # ★高額案件を「締切間近」だけで捨ててはいけない。
        #   締切前日でも 5,000円 の案件なら今日やる価値がある。緊急枠で人間へ。
        if (offer.advertised_yen or 0) >= 3000:
            return True, "締切間近だが高額 → 緊急で人間へ"
        return False, "期限切れ間近（判定期日が締切を超える）"
    if offer.advertised_yen is None:
        # ★重要: 金額不明を「低額」とみなして捨ててはいけない。
        #   高単価案件ほど「大幅アップ中」等の煽り表記で金額が構造化されていない。
        #   安価な抽出だけ回す軽量レーンへ送る。
        return True, "金額未構造化 → 抽出レーンへ"
    if offer.advertised_yen < MIN_REWARD_YEN:
        return False, f"報酬 {offer.advertised_yen:.0f}円 < {MIN_REWARD_YEN:.0f}円"
    if offer.category in ("app", "survey") and offer.advertised_yen < 1000:
        # 自動操作禁止領域かつ低単価。人間がやっても時給が成立しない。
        return False, "低単価の app/survey（人力でも時給割れ）"
    return True, "通過"


def cheap_hourly_estimate(offer: Offer, est_minutes: float) -> float:
    if offer.advertised_yen is None:
        return float("inf")   # 不明なものは落とさず次段へ
    return (offer.advertised_yen - offer.cost_yen) / max(est_minutes, 1.0) * 60


# ------------------------------------------------------------------
# 段階3: ファクトチェック（AI の回答ではなく、証拠から計算する）
# ------------------------------------------------------------------


def compute_fact_score(evidences: list[Evidence], advertised: float | None) -> FactReport:
    """fact_score = ソース品質 × 証拠の強さ × 相互一致 × 鮮度.

    ★AI に「信頼できますか?」と聞いてスコアを言わせない。
      証拠オブジェクトから決定論的に計算する。AI の仕事は証拠の収集と抽出まで。
    """
    if not evidences:
        return FactReport(fact_score=0.0, contradictions=["証拠ゼロ"])

    best_tier = max(e.tier for e in evidences)
    source_quality = best_tier

    # 証拠の強さ: 金額を明示している証拠の割合
    with_value = [e for e in evidences if e.claimed_yen is not None]
    evidence_strength = min(1.0, len(with_value) / 3.0) if with_value else 0.2

    # 相互一致: 上位ソース同士で金額が揃っているか
    contradictions: list[str] = []
    agreement = 1.0
    verified = None
    if with_value:
        # ★報酬額は公式級ソースの中の「最小値」を採る。
        #   「最大20%還元」の 6,000円 と規約上の上限 900円 が併存するとき、
        #   期待値計算に入れてよいのは 900円 の方。楽観側を採ると必ず外す。
        official = [e for e in with_value if e.tier >= SOURCE_OFFICIAL_MIN]
        basis = official or with_value
        # ★最小値ではなく「下側中央値」を採る。
        #   最小値だと、LLM の桁誤読（9,000→900）が1件混じるだけで報酬額が
        #   10分の1になり、優良案件が DROP される（シミュレーションで発生）。
        #   下側中央値なら、外れ値1つには耐えつつ保守側に倒れる。
        vals = sorted(e.claimed_yen for e in basis)
        verified = vals[(len(vals) - 1) // 2]

        # ★矛盾判定は公式級ソース同士でのみ行う。
        #   口コミ層(tier 0.40)は元々ばらつくもので、これを矛盾として数えると
        #   ほぼ全案件に contradiction が立ち、AUTO ゲートが常時閉じて
        #   全件が人間に流れる（＝通知疲れでシステムが死ぬ）。
        #   シミュレーションで実際にこの挙動が出た。
        devs = sorted(abs(e.claimed_yen - verified) / max(verified, 1.0) for e in basis)
        med = devs[len(devs) // 2]
        floor = 0.5 if any(e.source_type == "official_terms" for e in official) else 0.0
        agreement = max(floor, min(1.0, 1.0 - med))
        if devs[-1] > 0.25:
            contradictions.append(
                f"公式ソース間で報酬額が乖離（保守値={verified:.0f}円 / 最大乖離{devs[-1]:.0%}）")
        if advertised is not None and verified < advertised * 0.7:
            contradictions.append(
                f"広告値{advertised:.0f}円に対し公式上の実額は{verified:.0f}円（上限条件あり）")

    # 鮮度: 古い情報は割り引く（キャンペーンは改悪が早い）
    freshest = min(e.freshness_days for e in evidences)
    freshness = 1.0 if freshest <= 7 else (0.9 if freshest <= 30 else 0.7)

    # 公式ソースが1つも無い場合は上限を設ける（個人ブログだけで信用しない）
    score = source_quality * evidence_strength * agreement * freshness
    if best_tier < SOURCE_OFFICIAL_MIN:
        score = min(score, 0.55)
        contradictions.append("公式ソースで裏が取れていない")

    # ★「相互検証」の実体は、独立した公式級ソースが何系統あるか。
    #   同じページを3モデルが読んでも系統は1つのまま＝検証されていない。
    independent = len({e.source_type for e in evidences if e.tier >= SOURCE_OFFICIAL_MIN})

    return FactReport(fact_score=round(score, 3), contradictions=contradictions,
                      verified_yen=verified, independent_sources=independent)


SOURCE_OFFICIAL_MIN = 0.90   # official_faq 以上を「公式で裏が取れた」とみなす


# ------------------------------------------------------------------
# 段階5: ROI（AI に金額計算をさせない）
# ------------------------------------------------------------------


def compute_roi(offer: Offer, fact: FactReport, trial: TrialReport,
                approval_prior: float, would_be_auto: bool) -> RoiReport:
    reward = fact.verified_yen if fact.verified_yen is not None else (offer.advertised_yen or 0.0)

    # 成功確率 = 承認確率 × 手順を完遂できる確率
    success = approval_prior * (1.0 - trial.error_probability)
    expected = reward * success - offer.cost_yen

    # リスク割引: 事実確度と自動化確度の不足分を割り引く。
    # ★Dry Run 不能（ログイン必須）の案件で trial_score=0 を掛けると期待値が
    #   ゼロになり、本来「人間がやれば普通に儲かる」高額案件を DROP してしまう。
    #   観測不能は「自動化できない」であって「価値が無い」ではない。
    risk_discount = fact.fact_score * (trial.trial_score if trial.observable else 1.0)
    risk_adjusted = expected * risk_discount

    total_min = trial.est_minutes
    # ★本質的な比較軸は「期待利益 / 人間が拘束される時間」
    #   自動実行なら人間は通知の承認だけ。同じ期待値でも人間時給が桁違いになる。
    human_min = 0.5 if would_be_auto else total_min

    return RoiReport(
        expected_yen=round(expected, 1),
        risk_adjusted_yen=round(risk_adjusted, 1),
        total_minutes=round(total_min, 1),
        human_minutes=round(human_min, 1),
        hourly_total=round(risk_adjusted / max(total_min, 0.1) * 60, 1),
        hourly_human=round(risk_adjusted / max(human_min, 0.1) * 60, 1),
        success_probability=round(success, 3),
    )


# ------------------------------------------------------------------
# 段階6: 合議（多数決を「決定」に使わない）
# ------------------------------------------------------------------


def aggregate(votes: list[Vote]) -> Consensus:
    """複数モデルの投票を集約する.

    ★多数決で実行を決めない。理由は2つ:
      1) 全モデルが同じ Web ページを読んでいる場合、誤りは相関する。
         3票一致は「3つの独立した検証」ではなく「1つの誤読が3回反射しただけ」。
      2) BLOCK の見逃しコストは EXECUTE の取り逃しコストより桁違いに大きい。
    したがって BLOCK は 1 票でも veto として成立させる（全会一致を要求しない）。
    一致率は confidence の材料としてのみ使う。
    """
    ok = [v for v in votes if v.parse_ok]
    if not ok:
        # 全モデルが JSON 崩れ = 「危険」ではなく「判断材料が無い」。
        # veto（BLOCK）ではなく、一致率0で AUTO ゲートを塞いで人間に回す。
        return Consensus(votes, agreement=0.0, correlated=True, veto=False, majority="HUMAN")

    counts: dict[str, int] = {}
    for v in ok:
        counts[v.decision] = counts.get(v.decision, 0) + 1
    majority = max(counts, key=lambda k: counts[k])
    agreement = counts[majority] / len(ok)

    keys = {v.source_key for v in ok if v.source_key}
    correlated = len(keys) <= 1 and len(ok) > 1

    veto = any(v.decision == "BLOCK" for v in ok)
    return Consensus(votes=votes, agreement=round(agreement, 3),
                     correlated=correlated, veto=veto, majority=majority)


# ------------------------------------------------------------------
# 段階7: 決定論ルールエンジン（唯一の実行判断者）
# ------------------------------------------------------------------

FACT_GATE = 0.90
TRIAL_GATE = 0.85
AUTO_MAX_YEN = 5000.0      # これを超える金額は必ず人間が見る


def block_gates(offer: Offer, fact: FactReport, trial: TrialReport) -> Optional[Decision]:
    """安全ゲート. ★必ず ROI 判定より前に評価すること.

    シミュレーションで発覚した実バグ:
      無料枠を節約するため「ROI が低ければ投票前に DROP」という早期打ち切りを
      入れたところ、詐欺案件（fact_score 0.28）が BLOCK ではなく DROP として
      処理された。実害は同じ（実行しない）ように見えるが、
        - ブラックリストに登録されない
        - 同じ案件が翌日また調査され、無料枠を食い続ける
        - 「なぜ実行しなかったか」の記録が『儲からないから』になり、
          後で閾値を緩めた瞬間に実行されうる
      という形で危険が残る。安全判定はコスト最適化に追い越させてはならない。
    """
    if not trial.automation_allowed and offer.category in ("app", "survey"):
        return Decision("BLOCK", "規約上の自動操作禁止領域", ["tos:automation_prohibited"])
    if fact.fact_score < 0.35:
        return Decision("BLOCK", "事実確度が低すぎる（詐欺・釣り案件の疑い）", ["fact:too_low"])
    if (offer.advertised_yen and fact.verified_yen is not None
            and fact.verified_yen < offer.advertised_yen * 0.15):
        # ★DROP ではなく BLOCK。実行しない点は同じでも、BLOCK ならブラックリスト
        #   に載り、翌日また同じ案件を調査して無料枠を食うことがなくなる。
        return Decision("BLOCK", f"広告値{offer.advertised_yen:.0f}円に対し公式実額"
                                 f"{fact.verified_yen:.0f}円（釣り案件）", ["fact:bait"])
    if trial.recurring and not trial.observable:
        return Decision("BLOCK", "継続課金だが解約条件を公開情報で確認できない",
                        ["risk:recurring_unverifiable"])
    return None


def decide(offer: Offer, fact: FactReport, trial: TrialReport,
           roi: RoiReport, cons: Consensus) -> Decision:
    t: list[str] = ["block_gates:pass"]

    # ---- veto（投票後にしか判定できない BLOCK） ----
    if cons.veto:
        return Decision("BLOCK", "いずれかのモデルが BLOCK を主張（veto）", t + ["consensus:veto"])

    # ---- DROP 判定（期待値不足） ----
    if roi.hourly_human < MIN_HOURLY_YEN:
        # ★DROP も「取り逃し」というコストを持つ判断。根拠が1系統しかない
        #   高額案件を、その1系統の抽出ミスだけで確定 DROP してはいけない。
        upside = max(offer.advertised_yen or 0.0, fact.verified_yen or 0.0)
        if fact.independent_sources < 2 and upside >= 3000:
            return Decision("HUMAN", f"低ROI判定だが金額の裏付けが{fact.independent_sources}系統のみ",
                            t + ["roi:weak_evidence"])
        return Decision("DROP", f"人間時給 {roi.hourly_human:.0f}円 < {MIN_HOURLY_YEN:.0f}円",
                        t + ["roi:below_min"])
    if roi.expected_yen <= 0:
        return Decision("DROP", "実費を差し引くと期待値が負", t + ["roi:negative"])
    t.append("roi_gates:pass")

    # ---- AUTO 判定（全ゲート通過が必要。1つでも欠ければ HUMAN） ----
    gates = {
        "fact_score>=0.90": fact.fact_score >= FACT_GATE,
        "trial_score>=0.85": trial.trial_score >= TRIAL_GATE,
        "automation_allowed": trial.automation_allowed,
        "dry_run_observable": trial.observable,
        "no_kyc": not trial.kyc,
        "no_payment": not trial.payment,
        "no_recurring": not trial.recurring,
        "no_captcha": not trial.captcha,
        "amount<=5000": (fact.verified_yen or offer.advertised_yen or 0) <= AUTO_MAX_YEN,
        "no_contradiction": not fact.contradictions,
        # ★「3モデルが一致した」ではなく「独立した公式系統が2つ以上ある」を要求する。
        #   同一ページを3モデルが読んだ一致は、検証ではなく誤読の反射。
        "independent_sources>=2": fact.independent_sources >= 2,
        "consensus>=2/3": cons.agreement >= 0.66,
        "deadline>=2days": offer.deadline_days >= MIN_DEADLINE_DAYS,
    }
    failed = [k for k, v in gates.items() if not v]
    if failed:
        return Decision("HUMAN", "自動実行ゲート未通過: " + ", ".join(failed[:3]),
                        t + [f"gate_failed:{len(failed)}"])

    return Decision("AUTO", f"全ゲート通過 / 人間時給 {roi.hourly_human:.0f}円",
                    t + ["gates:all_pass"])
