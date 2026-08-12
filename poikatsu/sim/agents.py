"""エージェント層（LLM が担当する領域）.

本番では LLMClient を実 API に差し替える。シミュレータでは MockLLM が
「観測ノイズ・楽観バイアス・JSON崩れ」を再現し、実運用での劣化を先に測る。

★モデル名をコードに埋め込まない。無料枠・モデル名は年単位で変わるため、
  設定で差し替えられる抽象に留める（config/models.json）。
"""
from __future__ import annotations

import random

from .models import (Consensus, Cost, Evidence, FactReport, Offer, RoiReport,
                     TrialReport, Truth, Vote)
from .engine import compute_fact_score


# ------------------------------------------------------------------
# モックLLM
# ------------------------------------------------------------------

class MockLLM:
    """1モデルぶんの挙動を模したもの.

    accuracy      : 正しい判断に到達する確率
    optimism      : 楽観バイアス（HUMAN/BLOCK にすべきものを AUTO と言う傾向）
    json_fail     : 構造化出力が壊れる確率（リトライで無料枠を消費する）
    """

    def __init__(self, name: str, accuracy: float, optimism: float, json_fail: float):
        self.name = name
        self.accuracy = accuracy
        self.optimism = optimism
        self.json_fail = json_fail

    def vote(self, rng: random.Random, expert_label: str, fact: FactReport,
             trial: TrialReport, roi: RoiReport, source_key: str) -> tuple[Vote, int]:
        """判断を1票返す. 戻り値の int は消費した LLM 呼び出し回数（リトライ込み）."""
        calls = 1
        if rng.random() < self.json_fail:
            calls += 1                               # 1回リトライ
            if rng.random() < self.json_fail:
                return Vote(self.name, "HUMAN", 0.0, parse_ok=False, source_key=source_key), calls

        if rng.random() < self.accuracy:
            decision = expert_label
        else:
            # 誤るときの方向に偏りを入れる（楽観バイアス）
            if rng.random() < self.optimism:
                decision = {"BLOCK": "HUMAN", "HUMAN": "AUTO", "DROP": "AUTO", "AUTO": "AUTO"}[expert_label]
            else:
                decision = {"AUTO": "HUMAN", "HUMAN": "DROP", "DROP": "HUMAN", "BLOCK": "BLOCK"}[expert_label]

        conf = min(0.99, max(0.35, rng.gauss(0.85 if decision == expert_label else 0.72, 0.08)))
        return Vote(self.name, decision, round(conf, 2), source_key=source_key), calls


def default_panel() -> list[MockLLM]:
    """無料枠モデル3枚の想定. 数値は実測して config で上書きする前提."""
    return [
        MockLLM("model_a_flash", accuracy=0.88, optimism=0.65, json_fail=0.02),
        MockLLM("model_b_free", accuracy=0.78, optimism=0.55, json_fail=0.08),
        MockLLM("model_c_fast", accuracy=0.74, optimism=0.60, json_fail=0.15),
    ]


# ------------------------------------------------------------------
# Deep Research Agent: 「回答」ではなく「証拠」を集める
# ------------------------------------------------------------------

SEARCH_QUERIES = ["公式", "条件", "ポイント付与", "利用規約", "改悪", "失効"]


def research(rng: random.Random, offer: Offer, truth: Truth,
             max_searches: int) -> tuple[FactReport, Cost, str]:
    """検索を実行し Evidence を収集する.

    戻り値の str は source_key（全モデルが同一ソースに依拠しているかの検出用）。
    """
    cost = Cost()
    evidences: list[Evidence] = []

    # 怪しい出所の案件には、そもそも公式ソースが存在しない
    has_official = offer.source_type != "scrape" or rng.random() < 0.3

    def extract(value: float | None) -> float | None:
        """LLM による金額抽出のノイズを再現する.

        軽微な誤差(±3%)は日常。7% の確率で桁を読み違える（12,000→1,200 など）。
        後者を矛盾検出が拾えるかがファクトチェッカーの実力になる。
        """
        if value is None:
            return None
        if rng.random() < 0.07:
            return value * rng.choice([0.1, 10.0])
        return value * rng.uniform(0.97, 1.03)

    n = min(max_searches, len(SEARCH_QUERIES))
    for q in SEARCH_QUERIES[:n]:
        cost.search_calls += 1
        if q == "利用規約" and has_official:
            evidences.append(Evidence(
                "official_terms", f"{offer.url}/terms", "規約本文", rng.randint(1, 20),
                claimed_yen=extract(truth.true_yen),
                mentions_automation_ban=not truth.automation_allowed,
                mentions_kyc=truth.requires_kyc,
                mentions_payment=truth.requires_payment,
                mentions_recurring=truth.recurring_billing))
        elif q == "公式" and has_official:
            evidences.append(Evidence(
                "official_campaign", f"{offer.url}/campaign", "キャンペーン本文",
                rng.randint(0, 10), claimed_yen=extract(offer.advertised_yen or truth.true_yen)))
        elif q == "ポイント付与" and has_official:
            evidences.append(Evidence(
                "official_faq", f"{offer.url}/faq", "付与条件", rng.randint(3, 40),
                claimed_yen=extract(truth.true_yen)))
        elif q == "条件":
            evidences.append(Evidence(
                "point_site", f"{offer.url}/detail", "案件詳細", rng.randint(0, 5),
                claimed_yen=extract(offer.advertised_yen)))
        elif q in ("改悪", "失効"):
            # 口コミは真値の周りに大きくばらつく（そのまま信じてはいけない層）
            noisy = truth.true_yen * rng.uniform(0.5, 1.6)
            evidences.append(Evidence(
                "review", f"https://sns/{offer.id}", "口コミ", rng.randint(1, 200),
                claimed_yen=round(noisy)))

    fact = compute_fact_score(evidences, offer.advertised_yen)
    fact.searches_used = cost.search_calls
    source_key = max(evidences, key=lambda e: e.tier).url if evidences else ""
    return fact, cost, source_key


# ------------------------------------------------------------------
# Trial Agent: 公開ページのみの Dry Run
# ------------------------------------------------------------------


def dry_run(rng: random.Random, offer: Offer, truth: Truth) -> tuple[TrialReport, Cost]:
    """本番実行はしない。公開ページで観測できる特徴だけを集める.

    ★ログインが必要な導線は Dry Run すらしない（規約とアカウント保全のため）。
      その場合 observable=False とし、「不明」を「問題なし」に読み替えない。
    """
    cost = Cost(browser_pages=1)

    # ログイン後にしか導線が無い案件は観測不能
    observable = not (truth.requires_kyc and offer.category in ("fx", "securities", "bank"))
    if offer.source_type == "scrape":
        observable = observable and rng.random() < 0.5

    if not observable:
        return TrialReport(
            observable=False, automation_allowed=False, steps=0,
            est_minutes=truth.true_minutes, captcha=False, kyc=truth.requires_kyc,
            payment=truth.requires_payment, recurring=truth.recurring_billing,
            error_probability=0.5, trial_score=0.0), cost

    cost.browser_pages += rng.randint(1, 3)
    steps = max(3, int(rng.gauss(truth.true_minutes * 0.8, 3)))
    est = max(1.0, rng.gauss(truth.true_minutes, truth.true_minutes * 0.15))
    err = min(0.6, max(0.01, rng.gauss(0.05 + steps * 0.004, 0.02)))

    # 検出漏れを再現（規約文言の見落としは 8%）
    detected_ban = (not truth.automation_allowed) and rng.random() > 0.08

    trial_score = (1.0 - err) * (0.5 if not truth.automation_allowed else 1.0)
    return TrialReport(
        observable=True,
        automation_allowed=not detected_ban,
        steps=steps, est_minutes=round(est, 1),
        captcha=truth.has_captcha and rng.random() > 0.05,
        kyc=truth.requires_kyc, payment=truth.requires_payment,
        recurring=truth.recurring_billing,
        error_probability=round(err, 3),
        trial_score=round(min(1.0, trial_score), 3)), cost
