# InfoBank記事自動制作システム 実装設計書 v2.0

対象：Claude Code / Claude Agent SDK / Canva MCP / Magnific MCP・API / Notion API / VPS / Python
基準日：2026-08-18
レビュー：`docs/infobank-article-factory-v2-review.md`（BLOCKER 2件・MAJOR 6件は本文に反映済み）

## 確定事項（2026-08-18 ユーザー確認済み）

1. **公開/会員比率**：公開 ≒ 2/3、会員限定 ≒ 1/3（v1のNotion転記どおり。v2.0初版の記述は反転していたため修正済み）
2. **サムネイル**：1記事につき**1枚**。3パターン（TYPE A/B/C）を記事ごとに交互使用。デザイン変更不可、文字と色味のみ変更
3. **ブランド表記**：「**InfoBank**」に統一。図表出所は「InfoBank作成」／「〜をもとにInfoBank作成」。InfoBase表記が混入したら `BRAND_NAME_CONFLICT`
4. **テスト記事（Phase 7 E2E）**：既存ABCマート一式（`samples/2026-08-18_abcmart/`）を充当
関連資料：`docs/infobank-article-automation.md`（v1検討レポート）、`docs/pipeline-design.md`（v1技術設計）
根拠資料：会員限定記事の設定方法.pdf ／ グラフ・図表作成のテンプレート_0602 (1).pptx（133スライド）／ InfoBankサムネイル参考画像3点

**注記（参照切れ）**：`docs/infobank-article-automation.md` と `docs/pipeline-design.md` はこのブランチには存在せず、`origin/claude/article-automation-info-site-3grv4v` にのみ存在する（本ブランチへは未マージ）。参照する場合は該当ブランチから取得すること。添付PPTX原本（14.7MB）も現時点ではセッションのscratchpadにしかなく、`templates/original_infobank.pptx` としてリポジトリへ格納する方法（Git LFS等）は未確定。

## 0. 結論

本システムは以下の役割分担で構築する。

```
Claude Code            → 開発・保守・デバッグ
Python + Agent SDK     → 本番オーケストレーション
Notion                 → 制作ルール・案件キュー
Research Subagents     → Deep Research / Fact Check
Evidence Ledger        → 事実の唯一の入力源
Writer                 → 記事原稿
Magnific               → AI画像生成・編集・高画質化
Canva MCP              → 文字・ロゴ・レイアウト・3案制作
Python + 元PPTX        → グラフ・図表・PPTX
QA / Human Review      → 納品
```

MagnificとCanvaの役割を混同しない。

- AI画像を作る → Magnific
- タイトル・ロゴ・レイアウトを組む → Canva
- 正確な数値を持つグラフ・図表 → Python + PPTX
- 記事と調査 → Claude
- 制御と検証 → Python

これを本システムの基本原則とする。

## 1. 今回確定できた制作ルール

### 1.1 添付PPTXから確認できるHard Rule

図表の基本構造（テンプレートpptx スライド2・31より）：

```
キーメッセージ
図表タイトル
図表・グラフ・オブジェクト
出所
InfoBankロゴ
```

テンプレート明記事項（スライド31）：

- キーメッセージ：28文字以内
- 図表タイトル：1行以内
- フォント：Meiryo UI
- タイトル以外：14pt

「記事タイトル26〜28文字」と「図表キーメッセージ28文字以内」は**別ルール**として管理する。同じvalidatorにしてはいけない。

## 2. 画像・図表の引用ルール

テンプレートpptx スライド32・34〜36に引用方法が定義されている（33は無関係のプレースホルダ）。

- 画像をそのまま引用：必ずキャプションを付け、引用元を記載し、リンクを埋め込む（パターン①）
- グラフやデータを引用した場合も同様（パターン②）
- 完全独自作成：`出所：InfoBank作成` とし、右下にInfoBankロゴを置く（パターン③）
- 外部データから独自グラフ作成：`出所：〇〇をもとにInfoBank作成` とし、元データへのリンクをタイトルに埋め込む（パターン④）

システム内部では必ず以下4種類に分類する。

```yaml
citation_type:
  DIRECT_IMAGE:       # パターン① 画像そのまま引用
  DIRECT_CHART:       # パターン② グラフ・データ引用
  INFOBANK_ORIGINAL:  # パターン③ 完全独自作成
  INFOBANK_DERIVED:   # パターン④ 外部データから独自作成
```

自動判定に任せず、図表生成前に確定させる。

## 3. 会員限定記事のHard Rule

添付PDF「会員限定記事の設定方法」より。記事そのものを「制限付き」に設定した上で：

```
FREE CONTENT

[content_control logged_in="true"]

MEMBER CONTENT

[/content_control]

[member_cta_buttons]
```

ショートコードはLLMが自由に生成しない。Pythonが最後に挿入する。

## 4. Notion側ルールの扱い

取得済み要件（暫定Hard Rule）：

```
記事タイトル：26〜28文字（「ベトナム」+象徴キーワード必須、複数案生成）
本文：1,500文字程度、H2複数+SEOキーワード
メタディスクリプション：80〜90文字
図表：2枚程度/記事、pptx形式で納品
公開設定：全体の約2/3を公開、残り約1/3を無料会員限定
サムネイル：Canvaの3パターンを交互使用（1記事1枚。デザイン変更不可、文字と色味のみ変更）
主情報源：NNA（自動ログイン・自動取得は実装しない。本文は手動テキスト投入）
Magnific：画像高解像度化が主用途（AI生成を使う場合もproviderはMagnificに限定）
納品先：テスト段階=Notion／本番=WordPress
```

指定Notion URLをクラウド環境から再取得できなかったため、本番運用開始時にNotion APIで再取得して確定させる。NotionはページをMarkdownとして取得するAPI（`GET /v1/pages/:page_id/markdown`、Enhanced Markdown）を提供している。

```
Notion → rules.md → Rule Parser → rules.yaml → hash
```

## 5. Rule Versioning

毎ジョブ開始時にルールをスナップショット化する。

```json
{
  "rule_version": "2026-08-18",
  "source_page_id": "...",
  "sha256": "...",
  "article_title_min": 26,
  "article_title_max": 28,
  "figure_key_message_max": 28,
  "free_ratio_target": 0.6667,
  "free_ratio_tolerance": [0.60, 0.70],
  "thumbnails_per_article": 1,
  "thumbnail_patterns": ["A", "B", "C"],
  "brand_display_name": "InfoBank",
  "image_generator": "magnific",
  "human_review_required": true
}
```

前回からNotion本文hashが変わった場合は `RULE_CHANGE_DETECTED` としてジョブを止める。Claudeに変更後ルールを推測させない。

## 6. Claudeの採用構成

本番は `Python + claude-agent-sdk`。Claude Code CLIを24時間開きっぱなしにしない。

Claude Codeの用途：開発／デバッグ／エージェント定義／MCP設定／テスト／障害調査。

## 7. Subagent構成

```
01 rule-auditor
02 source-analyst
03 primary-researcher
04 independent-researcher
05 evidence-compiler
06 writer
07 fact-checker
08 critic
09 visual-director
10 citation-auditor
11 pptx-qa
```

## 8. 最重要：調査AIと執筆AIを完全分離

Writer自身にWeb検索をさせない。

```
Researcher A / B / C → Evidence Ledger → Writer → Fact Checker → Critic
```

Writerが使用できる事実は `status = VERIFIED` のEvidenceのみ。

## 9. Deep Research構成

- **Primary Researcher** 優先順位：政府／省庁／中央銀行／統計局／企業公式／IR／法令／規制当局／国際機関
- **Independent Researcher**：主要通信社／主要新聞／業界専門媒体／調査会社／現地報道
- **Source Analyst**：NNA等、依頼元の記事を解析し、人物・企業・数字・日付・政策・投資・市場・予測・主張をclaim単位に分解する。

**原則（v1より復活）**：NNAは有料購読サービスであり、二次利用が契約上どこまで許されるかは
着手前にクライアント確認が必要な論点（Phase 0の必須確認事項）。したがって
`source_loader.py` は **NNAへの自動ログイン・自動取得のコードを書かない**。入力は
人が本文を貼り付けたテキストファイル（`queue/<job_id>.txt`）として受け取る。

## 10. Evidence Ledger

調査結果を文章で保存しない。必ず構造化する。

```json
{
  "claim_id": "C017",
  "claim": "ベトナム政府は2026年GDP成長率を...",
  "claim_type": "number",
  "source_type": "primary",
  "source_url": "...",
  "quote": "原文からの該当箇所の直接引用",
  "lang": "vi",
  "published_at": "...",
  "retrieved_at": "...",
  "status": "VERIFIED",
  "confidence": 0.98
}
```

`quote` と `lang` は人間の最終ファクトチェック（7〜10分／記事）の原資になる。
これが無いと「AIが要約した文」しか残らず、原文と照合できない。

Writerは `evidence.json` しか読めない。

## 11. Double Fact Check

強制Double Check対象：数字／金額／割合／日付／企業名／人名／肩書き／法令／政策／投資額／市場規模／GDP／為替／予測／ランキング。

原則：`一次情報1件 + 独立情報1件` または `権威ある一次資料1件`。

情報が食い違った場合は `SOURCE_CONFLICT` として停止。AIが多数決で決めてはいけない。

## 12. Claim Audit

記事完成後、Fact Checkerが本文を再分解し、全claimをEvidence IDと照合する。Evidence IDが存在しない事実が1つでもあれば `UNSUPPORTED_CLAIM` としてWriterへ戻す。

## 13. 記事タイトルvalidator

LLM任せにせずPythonで検証する。NFC正規化後に文字数判定。v1のNotion転記にあった定量要件
（`samples/2026-08-18_abcmart/validate.py` で実装・PASS実績あり）をrule_id体系として統合する。

| rule_id | 検証内容 | 期待値 |
|---|---|---|
| T01 | タイトル文字数（NFC正規化後） | 26〜28字 |
| T02 | 「ベトナム」含有 | タイトル全案で必須 |
| T03 | タイトル案の数 | 3案以上（1案だと文字数リトライで詰まる） |
| M01 | メタディスクリプション文字数 | 80〜90字 |
| B01 | 本文文字数（公開+会員の合計） | 1,275〜1,725字（1,500字±15%） |
| B02 | H2見出しの数 | 2本以上 |
| B03 | 各H2のSEOキーワード含有 | 全H2で必須 |

```python
assert 26 <= article_title_length <= 28
assert "ベトナム" in article_title
```

`T01`/`T02`が不合格なら `TITLE_LENGTH_FAIL` としてタイトルのみ再生成。本文は再生成しない。
`B01`〜`B03`が不合格なら `BODY_LENGTH_FAIL` / `H2_FAIL` として該当部分のみ再生成する。

## 14. 図表validator

記事タイトルとは別に検証する（テンプレートのHard Rule）。

| rule_id | 検証内容 | 期待値 |
|---|---|---|
| F01 | 図表の枚数 | 2枚程度/記事 |
| F02 | キーメッセージ文字数 | 28字以内 |
| F03 | 図表タイトルの行数 | 1行以内（2段階検証・下記） |

```
figure_key_message_length <= 28
```

`figure_title_lines == 1` は静的検証だけでは判定できない（python-pptxはレンダリング後の
折返し行数を測れない）。したがって2段階で判定する。

1. **一次判定**（生成直後・機械的）：改行文字（`\n`）を含まない、かつテンプレート実測で
   較正した `max_chars`（フォント・枠幅から逆算した上限文字数）以内であること
2. **最終判定**（§33 Visual QA）：LibreOffice renderのPNGを見て、実際に1行で収まっているか
   Visual QA Agentが確認する

一次判定だけでPASS扱いにしない。折返し事故は最終判定でのみ確実に検出できる。

## 15. 会員限定比率

**`free ≒ 2/3、member ≒ 1/3`**（確定事項1）を構造的に作る。記事JSONを最初から `free_sections` / `member_sections` に分ける。文字列を機械的に切断しない。

公開部分：ニュース概要／重要ポイント／背景・経緯（本文の60〜70%）。
会員部分：分析・数字の深掘り・市場背景・今後の示唆（残り30〜40%）。

validator：NFC正規化後の文字数で `0.60 <= free/total <= 0.70`（前回サンプルのG01と同一基準）。

添付PDFは会員限定比率を定義しておらず、ショートコードの設定方法のみ規定。

## 16. Magnificを画像生成の唯一のAI画像系統にする

ChatGPT Image / DALL-E / Canva AI Image等を本番生成経路から外す。**AI画像を生成するなら
provider は必ずMagnific** とする（`IMAGE_PROVIDER_VALID`）。

ただしこれは「AI生成画像を必ず使う」という意味ではない。v1の転記では、Magnificの主用途は
**現地メディア画像の高解像度化**であり、Notionルールは現地メディア画像の転載自体を出所・
リンク明記のもとで許可している（§2 DIRECT_IMAGE/DIRECT_CHART）。報道記事でAI生成画像を
常用する方針は編集判断であり、システムが勝手に決めない。したがって：

- 現地メディア画像を引用する記事 → Magnificでアップスケールするだけでよい。AI生成は不要
- 独自ビジュアルが必要な記事 → AI画像生成を使う場合はproviderをMagnificに限定する
- `IMAGE_PROVIDER_VALID` は「生成画像が存在する場合にのみ provider==magnific を強制する」
  条件付きゲートとする。無条件の `MAGNIFIC_USED` にはしない

AI生成画像を使うかどうか自体の編集方針はPhase 0の確認事項。

Magnificは画像生成・編集・アップスケール・拡張・リライティング・MCP・APIを提供。Magnific MCPはClaude Codeをサポートし、エンドポイントは `https://mcp.magnific.com`。

## 17. Magnificの実装注意点

Auto modeではモデルが自動選択され、使用モデル名を結果から判別できない場合がある。再現性が重要な本番では `MODEL=AUTO` を原則禁止し、以下を保存する。

```json
{
  "provider": "magnific",
  "model": "...",
  "prompt": "...",
  "seed_or_job_id": "...",
  "created_at": "...",
  "source_refs": []
}
```

量産フェーズではMCPよりMagnific APIを優先する。

## 18. Magnificへ文字を描かせない

Magnificには背景写真・人物・都市・工場・農地・エネルギー設備・経済イメージだけ作らせる。

禁止：日本語タイトル生成／InfoBankロゴ生成／企業ロゴ生成／数字入り画像／グラフ生成。

文字とロゴは必ずCanvaで後付けする。これにより文字化け・偽ロゴ・数字誤り・架空企業名を防ぐ。

## 19. Canvaの役割

Canva Remote MCPはデザイン作成・編集・検索、アセット管理、Brand Kit、Export（PPTX含む）を提供する。

```
Magnific → background.png → Canva（title/logo/label/frame/brand colors）
        → thumbnail 1枚（TYPE A/B/Cを記事ごとにローテーション）
```

注意（外部仕様検証済み）：テンプレートへのデータ流し込み（brand template dataset + autofill）は
**Canva Enterprise限定**、Brand Template系ツールは**Pro以上**。プランをPhase 0で確認し、
Enterpriseでない場合は「デザイン複製＋edit-designによるテキスト置換」をフォールバックとする。

## 20. Canva Dev MCPとRemote MCPを混同しない

制作本体に使うのは **Canva Remote MCP**（`https://mcp.canva.com/mcp`）。Dev MCPはCanvaアプリ開発支援用。

## 21. Claude Code MCP設定

```bash
claude mcp add --transport http --scope project canva https://mcp.canva.com/mcp
claude mcp add --transport http --scope project magnific https://mcp.magnific.com
```

その後 `/mcp` からOAuth認証する。

## 22. Canva 3パターン

**1記事につきサムネイルは1枚**（確定事項2）。3パターンを記事ごとに交互使用し、デザインは変更せず文字と色味のみ差し替える。直近記事とパターンが重複しないことをvalidatorで検証する（`thumbnail_pattern_rotation`）。

参考画像から抽出したstyle archetype：

- **TYPE A（ニュース・経済型）**：複数写真コラージュ／強い帯／大型数字／大型タイトル／InfoBankロゴ
- **TYPE B（企業・ESG型）**：企業ロゴ／大きな背景写真／ブランドカラー／白いタイトルボックス／InfoBankロゴ
- **TYPE C（解説型）**：一枚写真／ブルーフレーム／巨大タイトル／カテゴリラベル／下部白帯／InfoBankロゴ

これらは正式ルールではなく、参考画像から抽出したVisual Referenceとして扱う。

## 23. Canvaテンプレート化

Canva上に `INFOBANK_COVER_A / B / C` を作る。

可変フィールド：`{{TITLE}} {{SUBTITLE}} {{KEY_NUMBER}} {{CATEGORY}} {{BACKGROUND}} {{PARTNER_LOGO}} {{INFOBANK_LOGO}}`

Claudeは位置を毎回自由設計せず、テンプレートへ値を流し込む方式を優先する。

## 24. グラフ・図表には生成AIを使用しない

GDP・人口・市場規模・為替・投資・輸出入・企業比較・ランキング等を画像生成AIへ描かせない（数字の改変・軸の誤り・存在しない値・文字化け・縮尺エラーが発生しうるため）。

```
Research data → validated JSON/CSV → Python → PPTX chart / table
```

## 25. 添付PPTXそのものをテンプレートエンジンにする

ゼロから似たPowerPointを作らない。`グラフ・図表作成のテンプレート_0602 (1).pptx` を原本とする（棒グラフ・表・バブル・ウォーターフォール・組織図・地図・ピラミッド・過去事例を含む）。

```
Original PPTX → Template Index → slide archetype選択 → 複製 → 文字置換 → データ置換 → 出所置換
```

## 26. python-pptx

既存chartがある場合は `既存chart style + replace_data()` を優先し、見た目を保持しながらデータだけ差し替える。可能な限りPNG貼り付けではなくPowerPoint chartを維持する。

**注意（E2E試作で判明）**: 「テンプレートを流用すれば書式は保たれる」は成り立たない。
原本の過去事例スライドは typeface を持たず、テーマ（Calibri / Segoe UI / 游ゴシック）へ
暗黙にフォールバックする。Meiryo UI を明示している定義スライドは基本テンプレート（slide2）だけ。
したがって生成後に **latin / ea / cs の3系統へ `Meiryo UI` を明示指定**し、
生成物のXMLを直接検査して `FONT_VALID` を判定すること。
同様に軸ラベルは規定どおり14ptへ揃える（24ptのままだとレンダラーが項目ラベルを間引く）。

## 27. PPTX Template Registry

最初に1回だけPPTXを解析しregistryを作成する。以後Claudeに133スライド全部を毎回読ませない。

```json
{
  "bar_chart": {"slide": 37},
  "table": {"slide": 39},
  "org_chart": {"slide": 119}
}
```

## 28. ブランド名の不整合

添付PPTXには `InfoBank`（14回：スライド2, 4-11, 35, 36, 115。うち小文字`Infobank` 2回）と `InfoBase`（8回：スライド31, 119-124, 129, 133）の両表記が存在する。

**正式表記は「InfoBank」に確定**（確定事項3）。`brand.yaml` に `display_name: InfoBank` を定義し、成果物（本文・図表・サムネイル）に `InfoBase` / `Infobank`（小文字）が混入した場合は `BRAND_NAME_CONFLICT` とする。テンプレート原本のInfoBase表記スライドを流用する際は出所行・ロゴを必ず置換する。

## 29. Article Schema

```json
{
  "article_id": "",
  "title": "",
  "lead": "",
  "free_sections": [],
  "member_sections": [],
  "claims": [],
  "figures": [],
  "thumbnail": {"pattern": "A|B|C", "image_path": "", "background_provider": ""},
  "sources": []
}
```

## 30. Figure Schema

```json
{
  "figure_id": "F01",
  "key_message": "",
  "title": "",
  "type": "bar",
  "data": {},
  "citation_type": "INFOBANK_DERIVED",
  "source_name": "",
  "source_url": "",
  "logo_required": true
}
```

## 31. Hooks

LLMの自主判断ではなくライフサイクル上で決定論的にコードを実行する。本番の実行主体は
Python worker（§6・§36）なので、これは**Agent SDKのhooks**（`ClaudeAgentOptions(hooks=...)`
に登録するPythonコールバック）で実装する。開発中はClaude Code Hooks（`settings.json`）で
同じvalidatorを流用して動作確認する。

```
Writer終了（SubagentStop）     → article_validator.py
Fact Check終了（SubagentStop） → claim_validator.py
Visual生成後（PostToolUse）    → visual_validator.py
PPTX生成後（PostToolUse）      → pptx_validator.py
Stop前（Stop）                 → final_gate.py
```

## 32. Final Hard Gates

以下が全てPASSするまで完成扱い禁止。1項目でも失敗した場合 `READY_FOR_HUMAN_REVIEW` へ進ませない。

```
RULE_HASH_VALID / SOURCE_AVAILABLE / RESEARCH_COMPLETE
ZERO_UNSUPPORTED_CLAIMS / ZERO_SOURCE_CONFLICT
ARTICLE_TITLE_VALID（26-28字・「ベトナム」含有・3案以上）
META_DESCRIPTION_VALID（80-90字） / BODY_LENGTH_VALID（1,500字±15%）
H2_VALID（2本以上・キーワード含有） / FIGURE_COUNT_VALID（2枚程度）
FIGURE_KEY_MESSAGE_VALID / FIGURE_TITLE_ONE_LINE / FONT_VALID（Meiryo UI）
FREE_RATIO_VALID（公開60-70%） / CITATION_VALID / BRAND_VALID（InfoBankのみ）
IMAGE_PROVIDER_VALID（生成画像が存在する場合はprovider==magnific）
THUMBNAIL_VALID（1枚・パターンローテーション） / LOGO_VALID
PPTX_VALID / VISUAL_QA_VALID
```

**テストモード規定**：Notion/Magnific/VPS等の外部接続が無い環境（本設計書のE2E試作環境を含む）
でも検証を止めないため、ゲートを2種に分ける。免除は「スタブで代替してPASSと記録する」ことで、
「検証しない」ことではない。スタブを使った旨は必ず成果物に記録する（§17の記録形式に準じる）。

| 分類 | ゲート | テストモードでの扱い |
|---|---|---|
| 免除可（外部接続依存） | RULE_HASH_VALID | Notion未接続時はv1転記＋確定事項からスナップショットを手作りしてhash化 |
| 免除可（外部接続依存） | IMAGE_PROVIDER_VALID | Magnific未接続時はプレースホルダ画像＋`provider: stub`で代替 |
| 免除可（外部接続依存） | SOURCE_AVAILABLE | NNA本文が既存の場合はそれを使う |
| **免除不可**（事実系） | ZERO_UNSUPPORTED_CLAIMS / ZERO_SOURCE_CONFLICT / CITATION_VALID / BRAND_VALID | 外部接続の有無に関わらず必ず検証する |
| **免除不可**（定量系） | ARTICLE_TITLE_VALID / META_DESCRIPTION_VALID / BODY_LENGTH_VALID / H2_VALID / FIGURE_COUNT_VALID / FIGURE_KEY_MESSAGE_VALID / FIGURE_TITLE_ONE_LINE / FONT_VALID / FREE_RATIO_VALID | 機械検証できるものを「未接続だから」で免除しない |
| **免除不可**（構造系） | THUMBNAIL_VALID / LOGO_VALID / PPTX_VALID / VISUAL_QA_VALID | 生成物そのものの検査であり外部接続に依存しない |

## 33. Visual QA

```
PPTX → LibreOffice headless → PDF → PNG → Visual QA Agent
```

検査対象：文字切れ／文字重複／改行事故／画像欠落／アスペクト比／ロゴ欠落／出典欠落／文字化け／フォント置換／グラフ軸／タイトル位置。

## 34. 状態機械

```
NEW → RULES_LOADED → SOURCE_LOADED → RESEARCHING → EVIDENCE_READY
→ DRAFT_READY → FACTCHECK_PASSED → MEMBERSHIP_BUILT → VISUAL_BRIEF_READY
→ IMAGE_READY → THUMBNAIL_READY → PPTX_READY → QA_PASSED
→ READY_FOR_HUMAN_REVIEW → APPROVED
```

失敗状態と復帰先・リトライ上限（v1の「最大3回→人間エスカレーション」を踏襲）：

| 失敗状態 | 発生する状態 | 復帰先 | リトライ上限 |
|---|---|---|---|
| `RULE_CHANGE_DETECTED` | RULES_LOADED | （人間が確認するまで停止。自動復帰しない） | 0 |
| `SOURCE_CONFLICT` | RESEARCHING | RESEARCHING（別の一次資料を探す） | 3回→人間エスカレーション |
| `UNSUPPORTED_CLAIM` | FACTCHECK_PASSED判定時 | DRAFT_READY（Writerへ戻す） | 3回→人間エスカレーション |
| `TITLE_LENGTH_FAIL` | DRAFT_READY判定時 | DRAFT_READY（タイトルのみ再生成、本文は再生成しない） | 3回→人間エスカレーション |
| `BODY_LENGTH_FAIL` / `H2_FAIL` | DRAFT_READY判定時 | DRAFT_READY（該当部分のみ再生成） | 3回→人間エスカレーション |
| `MEMBER_FAIL` | MEMBERSHIP_BUILT判定時 | FACTCHECK_PASSED（切り分けをやり直す） | 3回→人間エスカレーション |
| `FIGURE_FAIL` | PPTX_READY判定時 | VISUAL_BRIEF_READY（図表を作り直す） | 3回→人間エスカレーション |
| `MAGNIFIC_FAIL` | IMAGE_READY判定時 | VISUAL_BRIEF_READY | 3回→人間エスカレーション |
| `CANVA_FAIL` | THUMBNAIL_READY判定時 | VISUAL_BRIEF_READY | 3回→人間エスカレーション |
| `PPTX_FAIL` | PPTX_READY判定時 | VISUAL_BRIEF_READY | 3回→人間エスカレーション |
| `QA_FAIL` | QA_PASSED判定時 | 直前の生成工程（不具合の種類による） | 3回→人間エスカレーション |
| `CITATION_FAIL` | QA_PASSED判定時 | VISUAL_BRIEF_READY（出所・引用を修正） | 3回→人間エスカレーション |
| `BRAND_NAME_CONFLICT` | いずれの状態でも | （人間が正式表記を確認するまで停止） | 0 |
| `UNKNOWN_REQUIREMENT` | いずれの状態でも | （推測せず停止。人間の回答を待つ） | 0 |

リトライ上限に達したジョブは `READY_FOR_HUMAN_REVIEW` へは進めず、`failure` 列を保持したまま
停止する。**注意**：`worker/state.py` の `attempts` は現在すべての遷移で加算される総カウンタ
であり、失敗種別ごとのリトライ回数を数えているわけではない。上記の「3回→人間エスカレーション」を
実際に強制するロジック（失敗状態が同一のまま3回続いたら停止する）は**未実装**。Phase 3で
`worker/__main__.py` の `step()` に実装する。

## 35. プロジェクト構成

```
infobank-article-factory/
├── CLAUDE.md
├── .mcp.json
├── .claude/
│   ├── agents/            # 11 subagents (.md)
│   └── settings.json
├── config/
│   ├── rules.yaml / brand.yaml / models.yaml / research.yaml / visual.yaml
├── src/
│   ├── orchestrator.py / notion_loader.py / source_loader.py
│   ├── researcher.py / evidence.py / article_builder.py / member_builder.py
│   ├── magnific.py / canva.py / pptx_builder.py / citation_builder.py
│   ├── delivery/
│   │   ├── notion.py       # テスト段階の納品先
│   │   ├── wordpress.py    # 本番の納品先。会員限定ショートコード込みで投稿
│   │   └── factsheet.py    # 人間の最終ファクトチェック用シート生成（v1 §7.11相当）
│   └── validators/
├── templates/
│   ├── original_infobank.pptx
│   └── template_registry.json
├── assets/
│   ├── infobank_logo/
│   └── visual_references/
├── data/
│   └── jobs.sqlite3
└── artifacts/
    └── JOB_ID/
```

## 36. VPS

```
Ubuntu / Python 3.11+ / Claude Agent SDK / LibreOffice / SQLite / systemd
```

常駐処理：`article-worker.service`。Claude Code CLIではなくPython workerを常時起動する。

実装は `ai/claude/infobank-factory/`（導入手順は同ディレクトリの README）。

- `deploy/install_vps.sh` … 冪等なインストーラ。LibreOffice・和文フォント・venv・
  Meiryo UI代替のfontconfigまで用意する。`worker.env` は上書きしない
- `deploy/article-worker.service` … `Restart=always` で自動復帰。ただし短時間に連続失敗したら
  停止して人間を待つ（暴走防止）。`LimitCORE=0` でコアダンプ経由の鍵漏洩も塞ぐ
- `worker/state.py` … 状態をSQLiteに保存。プロセスが落ちても再起動で続きから再開する。
  `source_url` のUNIQUE制約で同一記事の二重処理を防ぐ（§37）
- `deploy/healthcheck.sh` … 死活・再起動回数・ジョブ状態・人間レビュー待ち件数を1画面で確認

**クラウド実行のセッションからVPSへは導入できない**（`ssh` クライアントも鍵も存在しない）。
導入はローカル実行のAIか手元の端末から1回だけ行う（AGENTS.md §6）。

## 37. Queue

Notion Databaseを制作キューにする（NEW / RESEARCH / REVIEW / APPROVED / ERROR）。Python側はNEWだけ処理。同一Source URL / Job IDを2回処理しない。

## 38. Secrets

ANTHROPIC_API_KEY / NOTION_TOKEN / CANVA TOKEN / MAGNIFIC_API_KEY / OAuth Token / Cookie / Session はClaudeの出力へ出さない。ログは `CANVA_AUTH=SET` 等のフラグのみ。

## 39. コスト制御

ジョブごとに `research_calls / claude_cost / magnific_credits / canva_operations` を記録。Magnific MCP経由の生成・変換はクレジットを消費するため、無限リトライは禁止。

## 40. 修正学習

人間の最終修正を `before / after / diff / reason / article_id / rule_version` で保存。頻出修正を `style_guide.md` へ昇格。ただし1回の修正だけでルールを変更しない。

## 41. 実装フェーズ

- **Phase 0 — Rule Freeze**：Notion API接続、正式ルール取得、ブランド名確定、**NNA二次利用の契約上の可否をクライアントへ確認**（v1 §6①の最大論点。技術で解決できない）、AI生成画像を使う編集方針の確認、Canvaプラン（Pro/Enterprise）の確認
- **Phase 1 — 既存PPTX解析**：template registry化
- **Phase 2 — Research Factory**：Subagents構築、Evidence Ledger完成
- **Phase 3 — Article Factory**：Writer / Critic / validator、会員限定ショートコード
- **Phase 4 — Visual Factory**：Visual Brief → Magnific → Canva A/B/C
- **Phase 5 — PPTX Factory**：図表JSONから既存テンプレートで生成
- **Phase 6 — QA**：PPTX render / Visual QA / Citation QA
- **Phase 7 — E2E Trial**：実案件1記事を最初から最後まで処理し、人間制作版と比較（Fact／文章／図表／出典／デザイン／PPTX／所要時間／コスト／人間修正量）

## 42. Claude Codeへの最終実装指示

```
この設計書を唯一の上位実装仕様として扱うこと。

1. 既存リポジトリ・VPSをまず読み取り専用で監査する。
2. 既存実装を壊さない。
3. 不明事項を推測しない。
4. NotionルールをAPIから取得する。
5. Rule hash機構を作る。
6. 添付PPTXをtemplate registry化する。
7. Custom Subagentsを構築する。
8. ResearcherとWriterを分離する。
9. Evidence Ledgerを実装する。
10. Double Fact Checkを実装する。
11. WriterにはWeb検索権限を与えない。
12. MagnificをAI画像生成の唯一のproviderとする。
13. Magnificには原則として文字やロゴを描かせない。
14. Canva Remote MCPで3デザインを生成する。
15. グラフ・図表は生成AIで作らない。
16. Pythonで元PPTXテンプレートを利用する。
17. 会員限定ショートコードはPythonで挿入する。
18. 引用4パターンを実装する。
19. 全validatorを作成する。
20. Hooksからvalidatorを強制実行する。
21. LibreOffice render QAを実装する。
22. 全テストを作成する。
23. 実案件1記事でE2E trialを行う。
24. HUMAN REVIEWより先へ自動で進まない。
25. APIキー・OAuth・Cookie等を一切ログ表示しない。

UNKNOWNな仕様を発見した場合は推測せず、
UNKNOWN_REQUIREMENTとして停止して報告すること。
```

## 43. 最終アーキテクチャ

```
                NOTION
                   │
             Rule / Queue
                   │
                   ▼
         PYTHON ORCHESTRATOR
                   │
         Claude Agent SDK
                   │
       ┌───────────┴───────────┐
       │                       │
 Research Agents          Source Analyst
       │                       │
       └───────────┬───────────┘
                   ▼
             EVIDENCE DB
                   │
                   ▼
                WRITER
                   │
          ┌────────┴────────┐
          ▼                 ▼
    FACT CHECKER          CRITIC
          └────────┬────────┘
                   ▼
             ARTICLE JSON
             │           │
             │           ▼
             │     FIGURE BUILDER
             │       Python/PPTX
             ▼
       VISUAL DIRECTOR
             │
          MAGNIFIC
             │
           CANVA
       A      B      C
             │
             ▼
          PPTX BUILD
             │
          RENDER QA
             │
        HUMAN REVIEW
```

## 44. 最終方針

「Claudeが記事を書いてCanvaで見た目を整えるシステム」として作らない。目標は、Source → Evidence → Article → Fact Check → Magnific → Canva → PPTX → QA の全工程を追跡可能にした、InfoBank専用のコンテンツ・プロダクションラインである。

```
LLMが得意なもの → LLM
画像生成       → Magnific
デザインレイアウト → Canva
数字・図表     → Python
決定論的検証   → Python / Hooks
最終判断       → 人間
```

これを崩さない。


> 状態名は `ai/claude/infobank-factory/worker/state.py` の `STATES` と一致させている。どちらかを変更したら両方を直すこと（ドリフト防止）。
