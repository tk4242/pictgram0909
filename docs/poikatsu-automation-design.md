# ポイ活 完全自動化システム 設計書

**構成**: ConoHa VPS (Ubuntu) + Python 3.11 + Claude Code (headless)
**方針**: BTC自動売買システム（`/opt/auto-trade`）と同じ運用流儀を踏襲する
**作成**: 2026-08

---

## 0. 最初に決める：「完全自動化」の対象範囲

ポイ活の収益源を分解すると、**自動化してよい領域とやってはいけない領域**がはっきり分かれる。
ここを混ぜると、システムが完成した瞬間に全ポイント没収・アカウント凍結で終わる。

| # | 収益源 | 年間規模の目安 | 自動化可否 |
|---|--------|--------------|-----------|
| 1 | 高額案件（クレカ発行・口座開設・FX・保険相談） | **30〜60万円** | 検知・比較・判断は自動 / **申込は本人必須**（本人確認・審査があるため物理的に不可） |
| 2 | ショッピング経由（ポイントサイト経由の買い物） | 消費額の1〜3% | 「買う前の最適経由ルート提示」を自動化 |
| 3 | 無料体験サービス（動画配信等） | 2〜5万円 | 検知＋**解約リマインド**を自動化 |
| 4 | ポイント交換ルート最適化 | 保有額の**+5〜15%** | **完全自動**（純粋な最適化問題） |
| 5 | 失効防止 | 年数千〜数万円 | **完全自動** |
| 6 | 紹介アフィリエイト／メディア運営 | 0〜月5万円 | **完全自動**（唯一の「寝てても増える」収益） |
| 7 | アンケート・ゲーム・広告クリック | 時給50〜300円 | **自動化禁止**（後述）。かつ費用対効果が最悪 |

### 自動化してはいけないもの（#7）とその理由

- **自動クリック / アンケート自動回答 / 自動アカウント登録 / 複数アカウント / エミュレータ農場**
  - 全ポイントサイトの規約で明確に禁止。発覚時は**未確定ポイント全没収＋アカウント削除**で、それまでの#1〜#6の資産も一緒に飛ぶ。
  - 「人間が作業した対価」として広告主が払っている報酬を、作業せずに受け取る構造なので、規約違反にとどまらない性質の問題を含む。
  - 技術的にも、現在のポイントサイトは行動ログ・端末指紋・滞在時間分布でBOT判定しており、**維持コストがリターンを上回る**。
- **ログイン後の会員ページを自動巡回するスクレイピング**も多くのサイトで規約上禁止。
  → 代替として本設計では **Gmail API による受信メールのパース**を主データ源にする。自分宛のメールを自分で読むだけなので規約的にクリーンで、しかも壊れにくい。

### 結論：本システムが実現する「自動化」の定義

```
完全自動  ： #4 交換ルート最適化 / #5 失効防止 / #6 アフィリエイト / 全案件の収集・採点・通知・台帳記帳
半自動    ： #1 #2 #3 → 「何を・いつ・どの経由で申し込むか」をシステムが決定し、
             人間は届いた通知を承認してクリックするだけ（月10時間 → 月1時間へ圧縮）
```

**狙いは「労働時間ゼロ」ではなく「実質時給を10倍にする」こと。**
最大の収益源#1が本人確認を必須とする以上、これが上限であり、逆にここを正しく設計すれば
「ポイ活に費やす時間を月1時間に抑えたまま年収+40万円」は現実的なターゲットになる。

---

## 1. システム全体構成

```
                    ┌──────────────────────────────────────────┐
                    │        ConoHa VPS (Ubuntu 22.04)          │
                    │                                            │
  Gmail API ───────▶│  collector/   案件・実績・失効の収集        │
  公開RSS/API ─────▶│      │                                     │
  公式キャンペーン ─▶│      ▼                                     │
                    │  normalizer/  名寄せ・重複排除              │
                    │      │                                     │
                    │      ▼                                     │
                    │   SQLite (poikatsu.db)  ◀── 単価履歴を蓄積  │
                    │      │                                     │
                    │      ├──▶ scorer/     期待時給スコアリング   │
                    │      ├──▶ optimizer/  交換ルート最適化       │
                    │      ├──▶ watchdog/   失効・解約期限監視     │
                    │      └──▶ ledger/     収益台帳・税務集計     │
                    │      │                                     │
                    │      ▼                                     │
                    │  notifier/  Discord Webhook / Telegram     │
                    │      │                                     │
                    │  publisher/ 記事・SNS自動投稿（#6）         │
                    └──────┼───────────────────────────────────┘
                           │
                     ┌─────▼─────┐        ┌────────────────────┐
                     │  スマホ通知 │◀──────│ Claude Code (cron) │
                     │  承認→申込 │        │ 日次レポート/自己修復│
                     └───────────┘        └────────────────────┘
```

### ディレクトリ構成（BTC システムと同じ流儀）

```
/opt/poikatsu/
├── systems/
│   ├── collector_gmail.py      # Gmail API から獲得/承認/失効メールをパース
│   ├── collector_offers.py     # 公開案件情報の収集（RSS/API/公開ページのみ）
│   ├── scorer.py               # 期待時給スコアリング
│   ├── optimizer.py            # ポイント交換ルート最適化（グラフ探索）
│   ├── watchdog.py             # 失効・無料体験解約期限の監視
│   ├── notifier.py             # Discord/Telegram 通知
│   └── publisher.py            # #6 アフィリエイト記事/SNS 自動投稿
├── libs/
│   ├── db.py                   # SQLite ラッパ
│   ├── gmail_client.py
│   ├── notify_client.py
│   └── rate_graph.py
├── config/
│   ├── poikatsu_config.json    # 閾値・重み・通知設定
│   ├── sites.yaml              # サイト定義・交換レート表
│   └── .env                    # APIキー（git管理外・chmod 600）
├── data/
│   └── poikatsu.db             # SQLite 本体
├── logs/
│   ├── poikatsu.log            # システムログ
│   ├── actions.csv             # 申込〜確定の全アクション台帳
│   └── revenue_ledger.csv      # 収益台帳（確定申告用）
└── reports/
    └── YYYY-MM.md              # Claude Code が生成する月次レビュー
```

---

## 2. データモデル（SQLite）

```sql
-- ポイントサイト
CREATE TABLE sites (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,   -- モッピー / ハピタス / ポイントインカム ...
  point_yen     REAL NOT NULL,          -- 1pt = 何円か（1.0 / 0.1 など）
  min_exchange  INTEGER,                -- 最低交換単位
  active        INTEGER DEFAULT 1
);

-- 案件マスタ
CREATE TABLE offers (
  id            INTEGER PRIMARY KEY,
  site_id       INTEGER NOT NULL REFERENCES sites(id),
  fingerprint   TEXT NOT NULL,          -- 正規化タイトル+カテゴリのハッシュ（サイト横断の名寄せキー）
  title         TEXT NOT NULL,
  category      TEXT,                   -- card / bank / fx / trial / shopping / insurance
  reward_yen    REAL NOT NULL,          -- 円換算した報酬
  condition     TEXT,                   -- 成果条件（原文）
  est_minutes   INTEGER,                -- 所要時間の推定
  cost_yen      REAL DEFAULT 0,         -- 年会費・最低入金などの実費
  deadline      TEXT,
  url           TEXT,
  first_seen    TEXT NOT NULL,
  last_seen     TEXT NOT NULL,
  status        TEXT DEFAULT 'open',    -- open / closed
  UNIQUE(site_id, fingerprint)
);

-- 単価履歴 ★ここが本システムの心臓部
CREATE TABLE offer_history (
  id            INTEGER PRIMARY KEY,
  offer_id      INTEGER NOT NULL REFERENCES offers(id),
  observed_at   TEXT NOT NULL,
  reward_yen    REAL NOT NULL
);
CREATE INDEX idx_hist_offer ON offer_history(offer_id, observed_at);

-- 実行アクション台帳
CREATE TABLE actions (
  id            INTEGER PRIMARY KEY,
  offer_id      INTEGER REFERENCES offers(id),
  status        TEXT NOT NULL,   -- candidate/applied/condition_met/pending/confirmed/rejected
  applied_at    TEXT,
  judge_due     TEXT,            -- 判定予定日（これを過ぎたら未反映として督促）
  expected_yen  REAL,
  confirmed_yen REAL,
  cancel_due    TEXT,            -- 無料体験の解約期限
  note          TEXT
);

-- 保有ポイント残高
CREATE TABLE balances (
  id            INTEGER PRIMARY KEY,
  site_id       INTEGER NOT NULL REFERENCES sites(id),
  points        REAL NOT NULL,
  expires_at    TEXT,
  updated_at    TEXT NOT NULL
);

-- ポイント交換の有向辺（最適化の入力）
CREATE TABLE exchange_edges (
  id            INTEGER PRIMARY KEY,
  from_site     TEXT NOT NULL,
  to_site       TEXT NOT NULL,
  rate          REAL NOT NULL,   -- 1pt → 何pt（増量キャンペーン込み）
  fee_points    REAL DEFAULT 0,
  min_unit      INTEGER DEFAULT 1,
  lead_days     INTEGER DEFAULT 0,
  campaign_end  TEXT,
  active        INTEGER DEFAULT 1
);

-- 承認確率の学習用（サイト×カテゴリごとの実績）
CREATE TABLE approval_stats (
  site_id       INTEGER,
  category      TEXT,
  applied       INTEGER DEFAULT 0,
  confirmed     INTEGER DEFAULT 0,
  PRIMARY KEY (site_id, category)
);
```

---

## 3. コアロジック

### 3.1 期待時給スコアリング（`scorer.py`）

BTC でいう「期待値（EV）」と同じ考え方。単純な報酬額の大きい順に並べても意味がない。

```python
EV_yen = reward_yen * p_approval - cost_yen
score  = EV_yen / (est_minutes / 60)        # 期待時給（円/h）
```

**承認確率 `p_approval` はベータ・ベイズ推定**（サンプルが少ない初期でも暴れないように）：

```python
# サイト×カテゴリの実績から。事前分布 Beta(2, 1) ≒ 「だいたい承認される」
p = (confirmed + 2) / (applied + 3)
```

カテゴリ別の初期値（実績が溜まるまでの事前値）:

| カテゴリ | 初期 p | 所要時間 | 備考 |
|---------|-------|---------|------|
| card（クレカ発行） | 0.85 | 20分 | 審査落ちリスクを織り込む |
| bank / securities | 0.90 | 30分 | 条件が明確で否認されにくい |
| fx（口座+取引） | 0.75 | 60分 | 取引条件の未達が多い |
| trial（無料体験） | 0.95 | 10分 | ただし解約忘れが最大の損失要因 |
| shopping | 0.80 | 3分 | Cookie の上書きで未反映が起きる |

### 3.2 「過去最高単価」検知 ★最大の差別化ポイント

同じ案件でも単価は月内で **1.5〜2倍** 変動する。**いつ申し込むか**が報酬を決める。
`offer_history` があれば、これは統計判定になる。

```python
def timing_signal(offer_id, current_yen):
    hist = fetch_history(offer_id, days=180)
    if len(hist) < 5:
        return "NEUTRAL"
    pct = percentile_rank(current_yen, hist)      # 0.0〜1.0
    if current_yen >= max(hist):     return "ALL_TIME_HIGH"   # 即申込を通知
    if pct >= 0.90:                  return "HIGH"            # 申込推奨
    if pct <= 0.40:                  return "WAIT"            # 待機（通知しない）
    return "NEUTRAL"
```

**`WAIT` の案件は通知しない**のが重要。通知が多すぎると人間が見なくなり、システム全体が死ぬ。
1日の通知は **`ALL_TIME_HIGH` / `HIGH` のみ、最大5件**にハードキャップをかける。

### 3.3 サイト横断の同一案件比較

同じ「楽天カード発行」がA社12,000円・B社9,000円ということが日常的に起きる。
`fingerprint` で名寄せし、**最高単価のサイトのURLだけを通知する**。

```python
fingerprint = sha1(normalize(title) + category)
# normalize: 全角半角統一・記号除去・「新規」「初回」等のノイズ語除去
```

### 3.4 ポイント交換ルート最適化（`optimizer.py`）— 完全自動領域

「モッピー → ドットマネー → 提携先」のように、経路次第で最終手取りが 1.0倍〜1.5倍 変わる。
**これは純粋な最適化問題で、人間の作業も規約上のグレーもゼロ。** 実質的な無料の利回り。

有向グラフの**最大レート経路**問題。手数料と最小単位があるので、単純な最短路ではなく実額で評価する：

```python
# 辺の重み: -log(rate) にすれば最短路（Bellman-Ford）で最大レート経路が解ける。
# ただし fee_points は定額のため対数変換と相性が悪い。
# 実運用ではサイト数が数十・経路長が3ホップ以内なので、DFS全探索で十分速い。

def best_route(from_site, to_goal, points, max_hops=3):
    best = None
    for path in enumerate_paths(from_site, to_goal, max_hops):
        p = points
        ok = True
        for edge in path:
            if p < edge.min_unit:            ok = False; break
            if edge.campaign_end and expired(edge.campaign_end): ok = False; break
            p = (p - edge.fee_points) * edge.rate
        if ok and (best is None or p > best.value):
            best = Route(path, value=p, days=sum(e.lead_days for e in path))
    return best
```

出力例（毎週日曜に通知）:

```
💱 交換ルート最適化
モッピー 12,400pt → 現金化
  推奨: モッピー → ドットマネー → 銀行  = ¥12,400（0営業日）
  直接: モッピー → 銀行                = ¥12,400（手数料 -¥0）
  ⚠ ハピタス 8,200pt は増量キャンペーン（+15%）が 8/20 終了 → 期限内に実行推奨
```

### 3.5 失効・解約期限の監視（`watchdog.py`）— 完全自動領域

**ポイ活で一番大きい「隠れ損失」は、失効と無料体験の解約忘れ。**
1件の解約忘れ（月額2,000円×気づくまで6ヶ月）で、高額案件1件分の利益が消える。

```
毎日 09:00 に判定：
  - balances.expires_at  <= 30日後 → 通知（交換ルート提案つき）
  - balances.expires_at  <= 7日後  → 毎日通知（エスカレーション）
  - actions.cancel_due   <= 3日後  → 🚨 最優先通知（解約手順URLつき）
  - actions.judge_due    < today かつ status='pending' → 「未反映」督促リストに追加
```

`judge_due` 超過の検知は地味だが効く。ポイントサイトの未反映は**自己申告すれば通ることが多い**が、
申告期限（多くは判定予定日から30〜90日）を過ぎると回収不能になる。手動管理では確実に取りこぼす。

### 3.6 Gmail パースによる実績自動記帳（`collector_gmail.py`）

ログイン後スクレイピングの代わりに、**自分宛のメールを主データ源にする**。

| メール種別 | 検索クエリ例 | 更新先 |
|-----------|------------|--------|
| ポイント獲得・承認 | `from:(moppy OR hapitas) subject:(獲得 OR 承認 OR 判定)` | `actions.status='confirmed'` |
| 失効予告 | `subject:(失効 OR 有効期限)` | `balances.expires_at` |
| 無料体験の登録完了 | `subject:(登録完了 OR お申し込みありがとう)` | `actions.cancel_due` を自動算出 |
| キャンペーン | `label:poikatsu newer_than:2d` | `exchange_edges.campaign_end` |

パースは正規表現で拾い、**取れなかったメールは `unparsed/` に退避して Claude Code が週次でパターンを追加する**（後述 4.2）。

---

## 4. Claude Code の組み込み方

BTC システムと同じく **headless モード（`claude -p`）を cron から叩く**。役割は4つ。

### 4.1 日次レポート／月次レビュー

```bash
# /etc/cron.d/poikatsu-report
30 8 * * * root cd /opt/poikatsu && \
  claude -p "$(cat prompts/daily_review.md)" \
  --allowedTools "Bash(sqlite3:*),Read,Write" \
  >> logs/claude_report.log 2>&1
```

`prompts/daily_review.md` の内容:
- 今日の `ALL_TIME_HIGH` 案件を、期待時給順に最大5件、理由つきで
- 期限切れ間近のもの
- 未反映の督促候補
- 今月の確定額 vs 目標

### 4.2 コレクタの自己修復

収集元のHTML構造やメール文面が変わるとパースが壊れる。BTC でいう「取引所API仕様変更」と同じ問題。

```bash
# 週次: unparsed が10件を超えたら Claude Code に修正させて PR を作らせる
0 3 * * 1 root cd /opt/poikatsu && \
  test $(ls data/unparsed | wc -l) -gt 10 && \
  claude -p "data/unparsed/ のメールを分析し、collector_gmail.py の
             パターンを追加してテストを通し、ブランチを切って push して" \
  --allowedTools "Read,Edit,Bash(pytest:*),Bash(git:*)"
```

### 4.3 アフィリエイト記事・SNS投稿の生成（#6 = 唯一の完全自動収益）

DBに溜まった**実データ**（単価推移・過去最高値・お得な交換ルート）は、そのままコンテンツになる。
一次情報を持っているので、他のポイ活ブログに対して構造的に強い。

```bash
# 週2回、実データから記事を生成 → 静的サイトへ push → 自動デプロイ
0 10 * * 2,5 root cd /opt/poikatsu && \
  claude -p "$(cat prompts/write_article.md)" --allowedTools "Read,Write,Bash(git:*)"
```

- **記事ネタは自動生成**：「今週 過去最高単価になった案件5選」「◯◯の交換ルート徹底比較（実測レート付き）」
- **紹介リンクは各サイトの紹介制度の規約に従う**（誇大表現・虚偽の実績表示は禁止。実データしか出さないので自然に守れる）
- **公開前に人間が承認するフローを1段挟む**ことを推奨（`drafts/` に出して、承認したら公開）。誤情報を自動公開すると信用を失うため。

### 4.4 モデル使い分け（BTC スキルと同じ運用）

| タスク | モデル |
|-------|-------|
| ログ確認・パターン追加・設定値変更 | Sonnet |
| スコアリング設計・月次レビュー・記事生成・複雑バグ | Opus |

---

## 5. 運用（systemd / cron）

BTC の `trade-btc.service` と同じ流儀で。常駐は不要なので **systemd timer** で十分。

```ini
# /etc/systemd/system/poikatsu-collect.service
[Unit]
Description=Poikatsu collector
[Service]
Type=oneshot
WorkingDirectory=/opt/poikatsu
ExecStart=/usr/bin/python3 systems/collector_offers.py
ExecStartPost=/usr/bin/python3 systems/collector_gmail.py
ExecStartPost=/usr/bin/python3 systems/scorer.py
ExecStartPost=/usr/bin/python3 systems/notifier.py
```

```ini
# /etc/systemd/system/poikatsu-collect.timer
[Timer]
OnCalendar=*-*-* 07,19:00:00     # 1日2回。高頻度アクセスは相手先に迷惑なので避ける
Persistent=true
[Install]
WantedBy=timers.target
```

| ジョブ | 頻度 | 内容 |
|-------|------|------|
| `poikatsu-collect.timer` | 1日2回 (07/19時) | 収集→採点→通知 |
| `poikatsu-watchdog.timer` | 毎日 09:00 | 失効・解約期限・未反映督促 |
| `poikatsu-optimize.timer` | 毎週日 10:00 | 交換ルート最適化 |
| `poikatsu-report`（cron） | 毎日 08:30 | Claude Code 日次レポート |
| `poikatsu-publish`（cron） | 週2回 | Claude Code 記事生成 |

### 収集時のマナー（必須）

- **公開ページのみ**。ログイン後の会員ページは巡回しない。
- `robots.txt` を尊重、**1リクエスト/3秒以上の間隔**、同一サイトへ1日2回まで。
- User-Agent に連絡先を明記。
- 各サイトの利用規約を導入前に確認し、スクレイピング禁止のサイトは **Gmail パースと公式RSS/APIのみ**に切り替える。
  実際、主要ポイントサイトはメールでキャンペーンを配信してくるので、これで実用上ほぼ足りる。

---

## 6. 収益台帳と税務（最初から作る）

**後から作ると絶対に破綻する。** Phase 0 で最優先に実装する。

```csv
# logs/revenue_ledger.csv
date,site,offer_title,category,expected_yen,confirmed_yen,cost_yen,net_yen,status
2026-08-05,モッピー,○○カード発行,card,12000,12000,0,12000,confirmed
2026-08-07,ハピタス,△△証券口座開設,securities,8000,0,0,0,pending
```

- ポイ活の収入は原則 **雑所得**（一時所得に該当するケースもある）。
  給与所得者は **年間20万円超で確定申告**が必要。本設計の想定規模（年30〜60万円）は**確実に対象**。
- 年会費・入金手数料などの `cost_yen` は経費計上の根拠になるので、必ず同時に記録する。
- 12月に「今年の確定額」「来年に判定がずれる分」を Claude Code に集計させ、申告用サマリを出す。
- **具体的な申告区分・控除の判断は税理士または税務署に確認すること。** システムは記録と集計までを担当する。

---

## 7. 導入フェーズと期待効果

| Phase | 期間 | 内容 | 効果 |
|-------|------|------|------|
| **0** | 1週 | SQLite + 収益台帳 + Gmailパース + 失効/解約 watchdog | **即効性最大**。解約忘れ・失効・未反映の取りこぼしがゼロになる |
| **1** | 2〜3週 | 案件収集 + `offer_history` + 過去最高単価通知 + サイト横断比較 | 同じ案件の単価が実質1.3〜1.5倍に。**ここが収益の主戦場** |
| **2** | 1〜2週 | 交換ルート最適化 | 保有ポイントに **+5〜15%** |
| **3** | 継続 | Claude Code による記事・SNS 自動運用 | 立ち上げ3〜6ヶ月はほぼゼロ、育てば月0.5〜5万円 |
| **4** | 継続 | 承認確率の学習、期待時給の精度向上、Claude Code 自己修復 | 通知の精度が上がり、人間の判断時間がさらに減る |

### 現実的な収益見込み（初年度）

```
#1 高額案件（システムが最適タイミングを提示、本人が申込）   月 2〜5万円
#2 ショッピング経由最適化                                消費額の1〜3%
#4 交換ルート最適化                                      保有ポイントの5〜15%
#5 失効・解約忘れの防止                                  年 1〜3万円（損失回避）
#6 アフィリエイト                                        初年度は期待しない
────────────────────────────────────────────────
合計：年 30〜60万円 / 投下時間 月1時間程度
```

**注意**: #1 は「1人1回」の案件が大半のため、**初年度は過去の未消化案件を消化できて多く、2年目以降は逓減する**。
BTC の複利とは性質が異なり、**ストックではなくフロー**。2年目以降を支えるのは #2 #4 #6 になる。
この逓減を前提に、Phase 3（メディア）を早めに仕込んでおくのが中期的な正解。

### ランニングコスト

| 項目 | 月額 |
|------|------|
| ConoHa VPS（BTC と同居可能・1GBで十分） | ¥0（既存流用）〜¥880 |
| Claude Code API（日次レポート＋週次記事） | ¥1,000〜3,000 |
| ドメイン（Phase 3のみ） | ¥100 |
| **合計** | **月 ¥1,000〜4,000** |

Phase 1 完了時点で回収できる水準。**BTC の VPS に同居させれば追加のサーバー費用はゼロ。**

---

## 8. 最初に着手する具体的な3ステップ

1. **`/opt/poikatsu/` を作り、SQLite スキーマと `revenue_ledger.csv` を作成**
   → 現在保有しているポイントサイトのアカウント一覧と残高を `sites` / `balances` に手入力（初回のみ）
2. **`watchdog.py` + Discord 通知を実装**
   → 失効・解約期限の通知が動いた時点で、既に元は取れている
3. **`collector_gmail.py` でメールパースを開始**
   → 1〜2ヶ月データを溜めてから `offer_history` の統計判定（3.2）を有効化する
   → **履歴が無いうちは「過去最高単価」判定が機能しない**ため、Phase 1 の効果は収集開始から1ヶ月遅れて出る

---

## 9. 設計上の注意点まとめ

- **通知疲れがシステムを殺す最大の要因。** 1日5件のハードキャップを必ず守る。「WAIT の案件は通知しない」。
- **`offer_history` が本システムの資産。** 収集は早く始めるほど価値が出る。他人には真似できない一次データになる。
- **#7（自動クリック等）には絶対に手を出さない。** 収益寄与が最小で、失うものが最大。
- **Gmail パースを主軸にする**ことで、規約リスクと保守コストの両方が下がる。
- **台帳を最初に作る。** 税務と、承認確率の学習データの両方がここから生まれる。
