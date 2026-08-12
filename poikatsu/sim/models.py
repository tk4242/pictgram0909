"""ドメインモデル.

本番では pydantic.BaseModel に置き換える（LLM 出力の JSON 検証のため）。
シミュレータは追加依存なしで動かしたいので dataclass で実装する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- 案件

CATEGORIES = ("card", "bank", "securities", "fx", "trial", "shopping", "survey", "app")

# 情報源の信頼度階層（他AI案 §5 のソース優先順位を数値化）
SOURCE_TIER = {
    "official_terms": 1.00,     # 公式利用規約
    "official_campaign": 0.95,  # 公式キャンペーンページ
    "official_faq": 0.90,       # 公式FAQ
    "point_site": 0.85,         # ポイントサイトの案件詳細
    "major_media": 0.70,        # 大手メディア
    "blog": 0.50,               # 個人ブログ
    "review": 0.40,             # 口コミ・SNS
}


@dataclass
class Offer:
    """Discovery が観測できる、案件の表向きの情報."""
    id: str
    title: str
    site: str
    category: str
    advertised_yen: Optional[float]   # None = 未構造化（報酬額が読み取れなかった）
    cost_yen: float = 0.0             # 年会費・最低入金などの実費
    deadline_days: int = 30
    source_type: str = "email"        # email / rss / official / scrape
    url: str = ""
    fingerprint: str = ""             # 案件の実体を指すキー。1人1回制約の判定に使う


@dataclass
class Truth:
    """シミュレータだけが知る真の状態. 精度評価の答え合わせに使う."""
    true_yen: float                   # 実際に支払われる額（広告値と乖離しうる）
    true_minutes: float
    approval_prob: float              # 条件を満たした場合に承認される確率
    automation_allowed: bool          # 規約上、自動操作が許可されているか
    requires_kyc: bool = False
    requires_payment: bool = False
    has_captcha: bool = False
    recurring_billing: bool = False   # 継続課金（解約忘れリスク）
    downgrade_risk: float = 0.0       # 条件改悪の確率
    label: str = "DROP"               # 人間専門家の正解ラベル AUTO/HUMAN/BLOCK/DROP


# ---------------------------------------------------------------- 調査・検証

@dataclass
class Evidence:
    source_type: str
    url: str
    snippet: str
    freshness_days: int
    claimed_yen: Optional[float] = None
    mentions_automation_ban: bool = False
    mentions_kyc: bool = False
    mentions_payment: bool = False
    mentions_recurring: bool = False

    @property
    def tier(self) -> float:
        return SOURCE_TIER.get(self.source_type, 0.3)


@dataclass
class Claim:
    text: str
    evidences: list[Evidence] = field(default_factory=list)
    agreement: float = 0.0     # ソース間の一致度
    confidence: float = 0.0


@dataclass
class FactReport:
    fact_score: float
    claims: list[Claim] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    verified_yen: Optional[float] = None   # 最上位ソースが主張する報酬額
    searches_used: int = 0
    independent_sources: int = 0           # 公式級ソースが何系統あるか（相互検証の実体）


@dataclass
class TrialReport:
    """公開ページのみを対象にした Dry Run の結果.

    observable=False は「ログインしないと判定できない」＝ Dry Run 不可能を意味する。
    その場合は自動実行の候補から外す（不明を『問題なし』と読み替えない）。
    """
    observable: bool
    automation_allowed: bool
    steps: int
    est_minutes: float
    captcha: bool
    kyc: bool
    payment: bool
    recurring: bool
    error_probability: float
    trial_score: float


@dataclass
class RoiReport:
    expected_yen: float          # 報酬 × 成功確率 - 実費
    risk_adjusted_yen: float
    total_minutes: float         # 作業時間の総量
    human_minutes: float         # ★人間が拘束される時間（AUTO ならほぼ 0）
    hourly_total: float
    hourly_human: float          # ★真の比較軸: 期待利益 / 人間介入時間
    success_probability: float


@dataclass
class Vote:
    model: str
    decision: str                # AUTO / HUMAN / BLOCK / DROP
    confidence: float
    parse_ok: bool = True
    source_key: str = ""         # 判断の根拠にしたソース（相関誤差の検出用）


@dataclass
class Consensus:
    votes: list[Vote]
    agreement: float
    correlated: bool             # 全員が同一ソースに依拠している＝独立でない
    veto: bool                   # 1票でも BLOCK があるか
    majority: str


@dataclass
class Decision:
    action: str                  # AUTO / HUMAN / BLOCK / DROP
    reason: str
    trace: list[str] = field(default_factory=list)


@dataclass
class Cost:
    """無料枠の消費量."""
    llm_calls: int = 0
    search_calls: int = 0
    browser_pages: int = 0

    def add(self, other: "Cost") -> None:
        self.llm_calls += other.llm_calls
        self.search_calls += other.search_calls
        self.browser_pages += other.browser_pages


@dataclass
class PipelineResult:
    offer: Offer
    truth: Truth
    stage: str                   # 到達した最終ステージ
    decision: Decision
    fact: Optional[FactReport] = None
    trial: Optional[TrialReport] = None
    roi: Optional[RoiReport] = None
    consensus: Optional[Consensus] = None
    cost: Cost = field(default_factory=Cost)
