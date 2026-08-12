# InfoBank 記事制作パイプライン 技術設計書

対象: [infobank-vn.com](https://infobank-vn.com/) ／ 版: 1.0 ／ 2026-08-12
前提資料: [検討レポート](./infobank-article-automation.md)

---

## 0. この設計が解く問題

本件は「AIに記事を書かせるシステム」ではありません。

> **NNAから渡された1本の記事を、仕様書で定められた形式の成果物（本文・タイトル・メタ・図表pptx・サムネイル・入稿設定）へ、毎回同じ品質で変換する制作ラインをつくる。**

難所は記事生成ではなく、**「26〜28字」「1,500字±」「図表2枚」「出所リンク必須」「会員限定2/3」「サムネ3パターン交互」といった定型制約を毎回外さないこと**です。したがって設計の重心は、生成側ではなく**検証側と描画側**に置きます。

---

## 1. 設計方針（5原則）

| # | 原則 | 具体的に何を意味するか |
|---|---|---|
| 1 | **AIは構造化データまでしか作らない** | Claudeが出力するのは `ArticleDraft` JSON のみ。本文HTML・pptx・PNG・WordPress投稿はすべてPythonが決定論的に描画する |
| 2 | **機械で判定できるものはAIに判定させない** | 文字数・要素数・URL到達性・重複率・分類IDの実在確認はPython。AIには「読んで分かること」だけ任せる |
| 3 | **すべての主張は evidence を参照する** | 段落・図表はすべて `evidence[]` のIDを持つ。持たない数値は検証で落ちる。これがファクトチェックシートの原資にもなる |
| 4 | **成果物は再現可能である** | どの原文・どのプロンプト版・どのモデル・どのテンプレート版から作られたかを全件記録する |
| 5 | **法的リスクのある動作は実装しない** | NNAへの自動ログイン・自動取得のコードは書かない。入力はテキストファイルで受け取る |

---

## 2. 自動化の境界

**結論：半自動です。完全自動にはしません。**

| | 工程 | 担当 |
|---|---|---|
| 1 | NNA記事本文の投入 | **人間**（約30秒／記事） |
| 2 | 現地ソース探索・背景リサーチ・データ収集 | 自動 |
| 3 | 本文・タイトル案・メタ・図表定義・分類の生成 | 自動 |
| 4 | 機械検証と自動リトライ | 自動 |
| 5 | AIレビュー3役と品質スコア | 自動 |
| 6 | 図表pptx生成・PNG化 | 自動 |
| 7 | サムネイル生成（3パターン交互） | 自動 |
| 8 | 現地メディア画像の高解像度化 | 自動 |
| 9 | Notion／WordPress下書き納品 | 自動 |
| 10 | 完了通知 | 自動 |
| 11 | 最終チェック | **人間**（7〜10分／記事） |
| 12 | 公開 | **人間** |

工程数ベースで約8割、作業時間ベースで約7割の自動化。**残す2工程は意図的に残します。** 仕様書に「最終的な事実チェックと自然な文章になっているかは目視が必要」と明記されており、自社メディアの信頼性に直結するためです。

---

## 3. システム構成

```
input/2026-08-12_semiconductor/
  source.txt        ← 人がNNA本文を貼り付け
  meta.yaml         ← url, 掲載日, 備考
        │
        ▼
┌──────────────────────────────────────────┐
│  run.py（オーケストレーター / Python）                       │
│                                                              │
│  ①research  → research.json    （Claude + Web検索）          │
│  ②write     → draft.json       （Claude）                    │
│  ③-a validate                  （Python・合否ゲート）         │
│        └ NG → 構造化フィードバックで②へ差し戻し（最大3回）    │
│  ③-b review → review.json      （Claude ×3・別コンテキスト）  │
│  ④render    → figures.pptx / figures/*.png / thumb.png       │
│  ⑤deliver   → Notion or WordPress（下書き）+ factsheet.md     │
│  ⑥notify                                                     │
└──────────────────────────────────────────┘
        │
        ▼
   data/articles.db（SQLite）
   ├ articles / runs / validations / reviews
   ├ corrections（人間の修正ログ）
   └ article_index（重複検知・内部リンク用）
        │
        ▼
   人間の最終チェック → 公開
```

---

## 4. データ契約 `ArticleDraft`

**このJSONが設計全体の背骨です。** Claudeの出力形式であり、検証の対象であり、描画の入力であり、ファクトチェックシートの原資です。Structured Outputs（`output_config.format`）でスキーマを強制します。

```jsonc
{
  "schema_version": "1.0",
  "article_id": "01JXYZ...",              // ULID

  "source": {
    "publisher": "NNA",
    "url": "https://www.nna.jp/news/...",
    "published_at": "2026-08-11",
    "text_sha256": "9f2a...",             // 原文のハッシュのみ保持
    "ingest_method": "manual_paste"       // 自動取得は実装しない
  },

  "titles": [                              // 3案以上
    { "text": "ベトナム電動バイクにペダル禁止案、規制強化へ",
      "chars": 27,
      "keywords": ["ベトナム", "電動バイク"] }
  ],

  "meta_description": "…80〜90字…",

  "lead": "…リード文…",

  "sections": [
    { "h2": "ベトナム二輪市場の構造変化",
      "keywords": ["ベトナム", "電動バイク"],
      "paragraphs": [
        { "id": "p1", "text": "…", "evidence": ["ev_1", "ev_4"] }
      ] }
  ],

  "gate_after": "p7",                      // 会員限定の区切り（全体の約2/3地点）

  "figures": [
    { "slot": 1,
      "layout": "bar_single",              // テンプレートのレイアウト名
      "key_message": "電動バイク比率は3年で2.4倍",
      "chart_title": "ベトナム二輪車販売に占める電動比率",
      "unit": "%",
      "series": [ { "label": "2023", "value": 8.1 },
                  { "label": "2024", "value": 13.6 },
                  { "label": "2025", "value": 19.4 } ],
      "source_label": "ベトナム統計総局（GSO）",
      "source_url": "https://www.gso.gov.vn/...",
      "evidence": ["ev_2"] }
  ],

  "images": [
    { "slot": 1,
      "url": "https://…",
      "caption": "ハノイ市内の電動バイク販売店",
      "source_label": "VnExpress",
      "source_url": "https://vnexpress.net/...",
      "upscale": true }
  ],

  "thumbnail": {
    "pattern": "B",                        // A/B/C を交互
    "line1": "ベトナム電動バイク",
    "line2": "ペダル禁止案の波紋",
    "accent": "#0F6FB8"
  },

  "taxonomy": { "category_id": 165, "tag_ids": [109, 166] },

  "internal_links": [
    { "anchor": "ベトナムのEV普及策", "article_id": "01JAB…",
      "url": "https://infobank-vn.com/…" }
  ],

  "evidence": [
    { "id": "ev_2",
      "claim": "2025年の電動比率は19.4%",
      "source_type": "gso",                // ホワイトリストの区分
      "source_url": "https://www.gso.gov.vn/...",
      "quote": "…原文引用…",
      "lang": "vi",
      "retrieved_at": "2026-08-12T09:03:00+09:00" }
  ]
}
```

**設計上の要点：**

- **段落と図表が `evidence` のIDを参照する構造**にしたことで、「全数値に出所があるか」が機械判定可能になります。原則3を実装している箇所です
- `source.text_sha256` だけを保存し、**NNA原文そのものはDBに残さない**選択ができます（保持期間ポリシーを設定可能）
- `gate_after` を段落IDで持つことで、会員限定の区切りが本文の何%地点かを検証できます

---

## 5. ディレクトリ構成

```
infobank-pipeline/
├── config/
│   ├── models.yaml            # モデルIDを一元管理（後述 §11）
│   ├── whitelist.yaml         # データソースのホワイトリスト
│   ├── taxonomy.yaml          # カテゴリ/タグID（WP APIから同期）
│   └── settings.yaml          # 閾値・リトライ回数・保持期間
├── prompts/
│   ├── research.v3.md
│   ├── writer.v5.md
│   ├── fact_checker.v2.md
│   ├── critic.v2.md
│   └── seo_checker.v1.md
├── style_guide/               # Phase 0 の成果物
│   ├── tone.md                # 文体・リード文の型・段落の長さ
│   ├── caption_format.md      # 「（説明文）（出所）〇〇「資料名」」
│   └── samples/               # 過去記事20本（プロンプトキャッシュ対象）
├── templates/
│   ├── chart_template.pptx    # 支給テンプレート（命名済みコピー）
│   ├── chart_template.map.yaml
│   └── thumbnails/{a,b,c}.html
├── src/
│   ├── run.py                 # オーケストレーター
│   ├── models.py              # ArticleDraft の Pydantic 定義
│   ├── llm.py                 # Claude API ラッパ（キャッシュ・課金記録）
│   ├── ingest.py              # ① 入力層
│   ├── research.py            # ② リサーチ層
│   ├── writer.py              # ③ 執筆層
│   ├── validators/
│   │   ├── __init__.py        # ルール登録とゲート判定
│   │   ├── text_rules.py      # T01-T03, M01, B01-B03
│   │   ├── evidence_rules.py  # E01-E03, C01
│   │   └── artifact_rules.py  # F01-F02, I01, G01, X01-X02, W01
│   ├── reviewers/
│   │   ├── fact_checker.py
│   │   ├── critic.py
│   │   ├── seo_checker.py
│   │   └── score.py
│   ├── render/
│   │   ├── charts.py          # python-pptx（Named Shape Mapping）
│   │   ├── pptx_to_png.py     # LibreOffice → PDF → PNG
│   │   ├── thumbnail.py       # Playwright
│   │   ├── upscale.py         # magnific API
│   │   └── layout_check.py    # Claude Vision で文字切れ検査（Phase 6）
│   ├── delivery/
│   │   ├── notion.py
│   │   ├── wordpress.py
│   │   └── factsheet.py
│   ├── store.py               # SQLite
│   └── notify.py
├── tools/
│   ├── inspect_pptx.py        # テンプレートの図形名を一覧
│   ├── sync_taxonomy.py       # WPからカテゴリ/タグID取得
│   └── log_correction.py      # 人間の修正を記録（§10）
├── input/                     # 記事ごとのフォルダ
├── output/
├── data/articles.db
└── logs/
```

**Dockerは最初は入れません。** VPSにPython・LibreOffice・Playwrightを直接入れて1本通し、環境再構築が面倒になった時点でコンテナ化すれば足ります。

---

## 6. データベース設計（SQLite）

```sql
CREATE TABLE articles (
  id              TEXT PRIMARY KEY,       -- ULID
  status          TEXT NOT NULL,          -- intake|research|writing|validating|
                                          -- reviewing|rendering|delivered|published|rejected
  source_url      TEXT,
  source_sha256   TEXT NOT NULL,
  source_pub_date TEXT,
  final_title     TEXT,
  wp_post_id      INTEGER,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

-- 再現可能性の中核。どの材料・どの版から作られたかを全件記録する
CREATE TABLE runs (
  id                  TEXT PRIMARY KEY,
  article_id          TEXT NOT NULL REFERENCES articles(id),
  stage               TEXT NOT NULL,      -- research|write|fact|critic|seo|render
  attempt_no          INTEGER NOT NULL,
  model_id            TEXT NOT NULL,      -- 実際に使ったモデルID
  prompt_version      TEXT NOT NULL,      -- writer.v5
  style_guide_version TEXT,
  template_version    TEXT,               -- chart_template.pptx の SHA-256
  validator_version   TEXT,
  input_sha256        TEXT NOT NULL,
  output_sha256       TEXT,
  input_tokens        INTEGER,
  cached_tokens       INTEGER,
  output_tokens       INTEGER,
  cost_usd            REAL,
  ok                  INTEGER NOT NULL,
  error               TEXT,
  started_at          TEXT NOT NULL,
  finished_at         TEXT
);

CREATE TABLE validations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id TEXT NOT NULL REFERENCES articles(id),
  attempt_no INTEGER NOT NULL,
  rule_id    TEXT NOT NULL,               -- T01, E03 ...
  severity   TEXT NOT NULL,               -- blocker|warn
  passed     INTEGER NOT NULL,
  field      TEXT,                        -- titles[0], figures[1].source_url ...
  actual     TEXT,
  expected   TEXT,
  message    TEXT
);

CREATE TABLE reviews (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id    TEXT NOT NULL REFERENCES articles(id),
  reviewer      TEXT NOT NULL,            -- fact|critic|seo
  score         INTEGER,
  findings_json TEXT NOT NULL,
  model_id      TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

-- 人間の修正ログ。プロンプト改善の原資（§10）
CREATE TABLE corrections (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id      TEXT NOT NULL REFERENCES articles(id),
  field           TEXT NOT NULL,          -- title|lead|sections[1].paragraphs[2]|figures[0].key_message
  correction_type TEXT NOT NULL,          -- fact|overstatement|tone|verbose|seo|source|figure|other
  before_text     TEXT,
  after_text      TEXT,
  note            TEXT,
  created_at      TEXT NOT NULL
);

-- 過去記事の重複検知と内部リンク候補の抽出に使う
CREATE TABLE article_index (
  article_id    TEXT PRIMARY KEY REFERENCES articles(id),
  title         TEXT NOT NULL,
  summary       TEXT NOT NULL,
  companies     TEXT,                     -- JSON配列
  keywords      TEXT,                     -- JSON配列
  url           TEXT,
  published_at  TEXT
);
```

---

## 7. 各層の仕様

### 7.1 入力層 `ingest.py`

```
input/<slug>/source.txt   NNA本文（人が貼り付け）
input/<slug>/meta.yaml    url / published_at / note
```

- **NNAへのHTTPアクセスを行うコードは書きません。** 自動ログイン・スクレイピングの実装を持たないこと自体が、リスク①への技術的な回答になります
- `source.txt` の SHA-256 を記録。`settings.yaml` の `source_retention_days` を過ぎたら本文を削除（ハッシュとURLは残す）
- 同一ハッシュの再投入は既存記事として検出し、重複制作を防ぐ

### 7.2 リサーチ層 `research.py`

Claude + Web検索ツール。出力は `research.json`。

- 探索対象：ベトナム語・英語の現地メディア、公的統計、企業IR
- **`whitelist.yaml` に載っていないドメインから取得した数値には `source_type: "other"` を付与**し、後段で「要確認」フラグの対象にする
- 「＋α」（背景・これまでの展開）はここで集める。`article_index` を参照し、既出テーマなら内部リンク候補も抽出する

```yaml
# config/whitelist.yaml（抜粋）
gso:        ["gso.gov.vn"]
customs:    ["customs.gov.vn"]
sbv:        ["sbv.gov.vn"]
multilateral: ["worldbank.org", "imf.org", "adb.org"]
ir:         ["aeon.info", "aeonmall.com", "global.honda", "vinfastauto.com"]
media_vn:   ["vnexpress.net", "tuoitre.vn", "thanhnien.vn", "vietnamnet.vn"]
```

### 7.3 執筆層 `writer.py`

- 入力：`research.json` ＋ `style_guide/`（プロンプトキャッシュ対象）＋ `source.txt`
- 出力：`ArticleDraft` JSON（Structured Outputs でスキーマ強制）
- タイトルは**3案以上**を必ず生成させる。1案しか出さないと、文字数リトライで詰まる

### 7.4 機械検証層 `validators/`

**合否ゲート。AIを介しません。**

| rule_id | 検査内容 | severity |
|---|---|---|
| `T01` | タイトル `26 ≤ len ≤ 28`（NFC正規化後のコードポイント数） | blocker |
| `T02` | タイトルに「ベトナム」を含む | blocker |
| `T03` | タイトル案が3件以上、かつT01/T02を通る案が1件以上 | blocker |
| `M01` | メタディスクリプション `80 ≤ len ≤ 90` | blocker |
| `B01` | 本文合計 `1275 ≤ len ≤ 1725`（1,500 ±15%） | blocker |
| `B02` | H2が2つ以上 | blocker |
| `B03` | 各H2にキーワードが1語以上含まれる | warn |
| `E01` | 数値を含む全段落が `evidence` を参照している | blocker |
| `E02` | 全 `source_url` がHTTP 200を返す | warn |
| `E03` | 図表データの `source_type` がホワイトリスト内 | warn → **要確認フラグ** |
| `C01` | 元記事との3-gram重複率が閾値未満（既定 8%） | blocker |
| `F01` | `figures` がちょうど2件 | blocker |
| `F02` | 各figureに key_message / chart_title / source_label / source_url がある | blocker |
| `I01` | 各imageに caption と source_url がある | blocker |
| `G01` | `gate_after` が本文の60〜70%地点にある | blocker |
| `X01` | pptx描画後、全プレースホルダが埋まり文字数上限内 | blocker |
| `X02` | サムネイルのパターンが直近2本と異なる（3種ローテーション） | warn |
| `W01` | `category_id` / `tag_ids` が `taxonomy.yaml` に実在する | blocker |

**リトライプロトコル**：blocker が1件でもあれば、構造化フィードバックを付けて執筆層へ差し戻します。

```json
{ "retry_reason": "validation_failed",
  "attempt": 2,
  "failures": [
    { "rule": "T01", "field": "titles[0]", "actual": 31, "expected": "26-28",
      "instruction": "3文字削って再提案。「ベトナム」は必須。" },
    { "rule": "E01", "field": "sections[1].paragraphs[2]",
      "actual": "evidence未参照", "expected": "1件以上",
      "instruction": "この段落の数値『前年比14%増』の出所をevidenceに追加するか、記述を削除。" }
  ] }
```

**最大3回**。3回で通らなければ人間にエスカレーションし、失敗内容を通知に含めます。「何度も直せない箇所」はプロンプト側の問題なので、`corrections` と併せて月次で棚卸しします。

### 7.5 AIレビュー層 `reviewers/`

**別コンテキストで3役を並列実行**（Claude Code のサブエージェント、または API のマルチエージェント構成）。

| 役 | 与える材料 | 見るもの | 配点 |
|---|---|---|---|
| **Fact-Checker** | `source.txt` ＋ `research.json` ＋ 本文<br>（**執筆時のやり取りは渡さない**） | 原文にない情報の混入、数値の飛躍、evidenceと本文の不一致、過剰な断定 | 30 |
| **Critic** | 本文 ＋ `style_guide/` | 論理の飛躍、誤解を招く表現、冗長さ、タイトルと本文の不一致 | 25＋20 |
| **SEO Checker** | 本文 ＋ `article_index` | H2キーワード、内部リンク候補、過去記事との重複・矛盾 | 10 |
| （Critic兼務） | 過去記事サンプル | トンマナ一致 | 15 |

**Fact-Checker に執筆時の文脈を渡さないことが要点です。** 同じ文脈を共有すると自分の出力を追認するだけになります。

**スコアは合否判定に使いません。** 用途は最終チェックの順序と注意箇所の提示に限定します。

### 7.6 図表生成 `render/charts.py` ★最重要

pptx描画は**このパイプラインで最も壊れやすい箇所**です。堅牢化のため次の設計を採ります。

**(1) Named Shape Mapping — 図形名で参照し、インデックスでは参照しない**

`slide.shapes[0]` のような位置指定は、クライアントがテンプレートを微修正した瞬間に全滅します。テンプレート側の各プレースホルダに固有名を付け、Python側は名前で検索します。

```yaml
# templates/chart_template.map.yaml
template_file:   chart_template.pptx
template_sha256: "3f8a91…"           # 起動時に照合する
layouts:
  bar_single:
    slide_index: 0
    shapes:
      IB_KEY_MESSAGE: { type: text,  max_chars: 40 }
      IB_CHART_TITLE: { type: text,  max_chars: 30 }
      IB_MAIN_CHART:  { type: chart, max_series: 1, max_categories: 8 }
      IB_SOURCE_NOTE: { type: text,  max_chars: 60 }
  line_trend:
    slide_index: 1
    shapes: { … }
```

```python
def find_shape(slide, name: str):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    raise TemplateContractError(
        f"図形 '{name}' がテンプレートに存在しません。"
        f"テンプレートが更新された可能性があります。"
        f"tools/inspect_pptx.py で図形名を再確認してください。"
    )
```

**起動時にテンプレートのSHA-256を照合し、不一致なら処理を止めて報告します。** 黙って別の場所に書き込むより、止まって知らせるほうが安全です。

**(2) グラフ実体の扱い — Phase 0 で判定する**

| | テンプレートの実装 | 対応 |
|---|---|---|
| **経路A（推奨）** | ネイティブのPowerPointグラフオブジェクト | `chart.replace_data(CategoryChartData(...))` で**数値だけ差し替え**。書式・配色・フォントは一切触らないのでトンマナが完全に保たれる |
| **経路B** | 図形の組み合わせで作図 | 各図形に命名して個別操作。バーの長さなど座標計算が必要になり保守コストが上がる |
| **経路C（最後の手段）** | 上記いずれも困難 | matplotlibで描画して画像として貼付。**トンマナ再現が難しくなるため極力避ける** |

支給テンプレートを受領したら、まず `tools/inspect_pptx.py` で全図形の `name` / `shape_type` / `has_chart` を出力し、A/B/Cを判定します。**これがPhase 0の最初の作業です。**

**(3) 文字あふれ対策**

python-pptx は描画後の実寸を測れません。したがって：

- マッピングYAMLの `max_chars` を**テンプレート実測で較正**し、検証ルール `X01` で機械的に弾く
- Phase 6 で pptx→PNG→Claude Vision による目視相当のレイアウト検査を追加（文字切れ・図形の重なり・見切れ）。Claudeは画像を読めるので**この用途にも外部ベンダーは不要**です

### 7.7 pptx → PNG `render/pptx_to_png.py`

WordPress貼付用のPNGを作ります。`--convert-to png` は先頭スライドしか出さないため、**PDFを経由します。**

```bash
soffice --headless --convert-to pdf --outdir out/ figures.pptx
pdftoppm -r 200 -png out/figures.pdf out/figure     # → figure-1.png, figure-2.png
```

### 7.8 サムネイル `render/thumbnail.py`

- `templates/thumbnails/{a,b,c}.html` に3パターンを再現（文字と色味のみ差し替え可能な構造）
- Playwright（Chromium）でPNG化。1枚1秒未満、完全に決定論的
- `X02` でパターンのローテーションを検証（直近2本と重複しない）
- 代替経路：Canva Pro の Bulk Create にCSVを渡す方式も可。Phase 0でどちらを採るか決めます

### 7.9 画像処理 `render/upscale.py`

magnific API で現地メディア画像を高解像度化。**キャプションは必ず `source_label` ＋ `source_url` を含む形で生成**し、`I01` で検証します。

### 7.10 納品層 `delivery/`

**Notion（テスト段階）** — 本文・図表PNG・サムネ・タイトル案・メタ・分類・スコアを1ページにまとめる。

**WordPress（本番）** — REST API ＋ Application Password で `status: "draft"` 投稿。**`publish` は決してコードから呼びません。**

```
POST /wp-json/wp/v2/media     ← アイキャッチ・図表PNGをアップロード
POST /wp-json/wp/v2/posts     ← status=draft, categories, tags, featured_media
```

会員限定の区切りは、支給資料「会員限定記事の設定方法.pdf」の方式（ショートコードかブロックか）を確認のうえ、`gate_after` の位置に挿入します。

**ファクトチェックシート `factsheet.md`** — 最終チェックの時間を決める成果物です。

```markdown
## 記事C — 品質スコア 78
### ⚠ 要注意
- 第3段落「輸出額は前年比14%増」→ 出所が VietnamNet（ホワイトリスト外・E03）
- H2「ベトナム 半導体」→ 2026-07-28 の記事と重複（SEO Checker）

### 段落ごとの根拠
| 段落 | 記述 | 根拠 | 出所 |
|---|---|---|---|
| p1 | 電動比率19.4% | ev_2 | GSO（原文引用付き） |
| p2 | ペダル禁止案 | ev_1 | NNA原文 第2段落 |
```

### 7.11 通知 `notify.py`

バッチ完了時に1通。

```
本日3件、下書き完了（Notion）
・記事A  92点  特記なし
・記事B  85点  要注意：第3段落の輸出額（出所がホワイトリスト外）
・記事C  78点  要注意：H2が過去記事と重複／リード文が冗長
・記事D  検証失敗（T01が3回連続でNG）→ 要手動対応
```

---

## 8. 再現可能性

「3ヶ月後に同じ入力から作った記事が別物になる」を防ぎます。`runs` テーブルに全実行の以下を記録：

| 記録項目 | 目的 |
|---|---|
| `model_id` | モデル更新による出力変化の切り分け |
| `prompt_version` | プロンプト改訂の効果測定 |
| `style_guide_version` | トンマナ定義の改訂追跡 |
| `template_version`（pptxのSHA-256） | テンプレート変更による描画崩れの原因特定 |
| `validator_version` | 検証ルール変更の追跡 |
| `input_sha256` / `output_sha256` | 同一入力・同一出力の確認 |
| トークン数・キャッシュヒット・コスト | 記事単価の実測 |

これにより「この成果物は、何を材料に、どの版で作られたか」が常に遡れます。品質低下が起きたとき、原因がモデルなのかプロンプトなのかテンプレートなのかを切り分けられるのが実利です。

---

## 9. 設定の一元管理

**モデルIDを各所にベタ書きしません。** 1ファイルに集約し、更新は1箇所で済むようにします。

```yaml
# config/models.yaml
default: &default
  provider: anthropic
  model: claude-opus-5          # 実行前に Models API で存在確認する
  effort: high

stages:
  research:  { <<: *default }
  writer:    { <<: *default }
  fact:      { <<: *default }
  critic:    { <<: *default }
  seo:       { <<: *default, model: claude-sonnet-5 }   # 軽量で足りる工程
  layout_check: { <<: *default }                        # Vision（Phase 6）

cache:
  # 全記事共通の前置き（スタイルガイド・過去記事・テンプレート定義）を
  # プロンプトキャッシュ対象にする。入力コストが約1/10になる
  cacheable_prefix: [style_guide, taxonomy, template_map]
```

起動時に `GET /v1/models` で `model` の実在を確認し、存在しなければ**起動時に落とします**（記事生成の途中で404を踏むより早く気づける）。

---

## 10. Human Correction Log と改善サイクル

最終チェックであなたが直した内容を記録し、プロンプトへ還元します。**ファインチューニングは不要です。**

```bash
# Notion/WPで修正したあと、1行で記録
$ python tools/log_correction.py 01JXYZ \
    --field "sections[1].paragraphs[2]" \
    --type overstatement \
    --before "同社は市場を独占している" \
    --after  "同社は市場で高いシェアを占めている"
```

月次で集計し、頻出パターンをプロンプトとスタイルガイドへ反映します。

```
2026年9月（48記事）
  tone         18件  ← 断定が強すぎる。writer.v6 に抑制指示を追加
  source        9件  ← ホワイトリスト外の出所。research.v4 で優先度を明示
  verbose       7件  ← リード文が長い。style_guide/tone.md に字数目安を追記
  fact          2件  ← 良好
  figure        1件
```

さらに `reviews.score` と実際の修正量の相関を見て、**AIスコアの較正**にも使います。スコアが高いのに修正が多い記事が続くなら、レビュアーのプロンプトが甘いということです。

---

## 11. 実装フェーズ

| Phase | 内容 | 所要 | 完了条件 |
|---|---|---|---|
| **0** | 権利確認・テンプレート解析・トンマナ抽出 | 2〜3日<br>（①は別途） | 下記 §12 の9項目 |
| **1** | 縦串1本：1記事をend-to-endでNotion納品 | 5〜7日 | サンプル1本の品質確認をいただく |
| **2** | 機械検証＋リトライループ | 3〜4日 | 全ルール実装、リトライで通ること |
| **3** | AIレビュー3役＋品質スコア＋ファクトチェックシート | 3〜4日 | 最終チェックが10分以内に収まること |
| **4** | 複数記事バッチ＋通知＋運用ログ | 2〜3日 | 1日3本を一括処理できること |
| **5** | WordPress下書き投稿 | 3〜5日 | 会員限定設定まで自動化 |
| **6** | 補正ログ→改善サイクル、Visionレイアウト検査 | 継続 | 月次で修正率が下がること |

**Phase 1 で「1本を完全に通す」ことを最優先します。** 大量処理も検証も、まず1本が通ってからです。

---

## 12. Phase 0 の作業項目

| # | 作業 | 必要なもの | 成果物 |
|---|---|---|---|
| 1 | **NNAコンテンツ利用権の確認** | クライアント→NNA | 可否の書面／合意ログ |
| 2 | pptxテンプレート解析（経路A/B/C判定） | テンプレートpptx | `inspect_pptx.py` の出力 |
| 3 | プレースホルダへの命名 | 同上 | `chart_template.pptx`（命名済）＋ `.map.yaml` |
| 4 | `max_chars` の実測較正 | 同上 | マッピングYAMLの数値確定 |
| 5 | 過去記事20本のトンマナ抽出 | 記事URL一覧 | `style_guide/tone.md`, `caption_format.md` |
| 6 | Canvaサムネ3パターンのHTML再現 | デザインファイル | `templates/thumbnails/{a,b,c}.html` |
| 7 | 会員限定設定方式の確認 | 設定方法PDF | 挿入マーカーの仕様 |
| 8 | カテゴリ/タグIDの同期 | WP認証情報 | `taxonomy.yaml`（**大部分は取得済**） |
| 9 | 検証項目を「機械／AI／人間」に分類 | 上記すべて | ルール表の確定 |

### 権利確認で押さえる項目（#1）

技術的な確認ではなく契約の確認です。以下を明示的に。

- AIへの入力可否
- 要約・翻訳・加工の可否
- 商用メディアへの二次提供の可否
- 会員限定コンテンツへの利用可否
- 自動取得・スクレイピングの可否
- 原文の保存期間
- 生成物の権利帰属

**#1の結果が出るまで、#2〜#9は並行して進められます。** #1が未確定でもテンプレート解析やトンマナ抽出は着手可能で、権利面がクリアになった時点で Phase 1 に入れる状態を作っておきます。

**入力設計は権利確認の結果を問わず「テキスト手動投入」に固定します。** 仮に自動取得が許諾されても、VPSのアカウント停止・IP規制のリスクが残り、得られるのは1記事あたり30秒だけです。割に合いません。

---

## 13. エラー処理と運用

| 事象 | 挙動 |
|---|---|
| 検証が3回連続で失敗 | 該当記事を `rejected` にし、失敗ルールを通知に含めて人間へ |
| テンプレートSHA不一致 | **処理を停止**し報告。黙って描画しない |
| モデルIDが存在しない | 起動時に落とす |
| Web検索・magnific のレート制限 | 指数バックオフで最大3回。超えたら該当記事のみスキップし、他は継続 |
| `source_url` が404 | `E02`（warn）としてファクトチェックシートに記載。処理は止めない |
| ホワイトリスト外の出所 | `E03`（warn）→ 通知とシートで**要確認**として明示 |
| WP API が401 | Application Password の失効。即通知 |

**方針：blocker以外では止めません。** 1本の不備で当日分がすべて止まるほうが運用上の損失が大きいためです。

---

## 付録：他案から取り込んだ実装レベルの指摘

| 指摘 | 反映先 | 評価 |
|---|---|---|
| **Named Shape Mapping**（インデックス指定を禁止し図形名で参照） | §7.6 | **採用。これが無いとテンプレート微修正で全滅します。**本設計で最も価値のある指摘 |
| 再現可能性のためのバージョン記録（prompt_version / template_version 等） | §6, §8 | 採用。品質低下時の原因切り分けに直結する |
| Human Correction Log（修正内容の分類記録） | §6, §10 | 採用。運用ログを「計測」から「改善の原資」に格上げした |
| リトライ回数の上限と構造化フィードバック | §7.4 | 採用。上限3回とエスカレーション先を明示 |
| モデルIDをベタ書きせず一元管理・実在確認 | §9 | 採用。`config/models.yaml` に集約 |
| Phase 0 に「NNA利用権確認」を明示的に含める | §12 | 採用 |
| Docker・PostgreSQL は初期から入れない | §5, §6 | 採用（前回レポートと同じ結論） |
| Vision によるレイアウト検査 | §7.6(3) | **採用。ただし Claude のVisionを使います** — 外部ベンダーを増やす理由がありません |
| 画像生成APIを本体に組み込まない | 全体 | 双方合意。本設計に画像生成は含みません |
