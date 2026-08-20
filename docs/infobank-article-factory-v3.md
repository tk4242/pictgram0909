# InfoBank記事自動制作システム 実装設計書 v3.0

基準日：2026-08-19 ／ 前版：`docs/infobank-article-factory-v2.md`（v2.0）
レビュー履歴：`docs/infobank-article-factory-v2-review.md`
E2E実測：`samples/2026-08-18_abcmart/e2e_report.md`（ABCマート越5号店で1記事完走済み）

> **本書の位置づけ**：新チャット・新セッションへ移行しても作業を継続できる「唯一の上位実装仕様」。
> v2.0との差分は §0.1 に集約。実装済み資産の棚卸しは §45 に集約。
> 本書はNotionにも複製する（複製の実施状況は docs/ai-worklog.md に記録。リポジトリ側=このファイルが常に正）。

## 0. 最終ゴール（今回確定）

**「記事リンクを貼るだけで、制作ルールに完全準拠した記事一式が自動で出来上がるアプリ」**

```
ユーザーがやること：
  1. NotionのキューDBへ NNA記事リンクを貼る（+必要なら本文貼付）
  2. 図表の引用パターンを承認する（システムが候補を提示。キューDBの「引用パターン」
     プロパティで確認。未承認のまま図表生成へは進まない＝CITATION_UNCONFIRMEDで待機）
  3. 出来上がった記事を人間レビューして承認する
それ以外の全工程（調査・執筆・検証・図表・サムネ・納品）はシステムが行う。
```

- **テスト段階**：記事はNotion上に作成し、**Notionで納品**する（今回確定）
- **本番段階**：WordPressへ下書き入稿（会員限定ショートコード込み）
- 人間レビュー（READY_FOR_HUMAN_REVIEW）より先へは自動で進まない。これは撤廃しない

### 0.1 v2.0からの主な変更点

| # | 変更 | 理由 |
|---|---|---|
| 1 | 納品先を「テスト=Notion納品」に確定し、delivery/notion.py を最優先実装に | ユーザー確定（2026-08-19） |
| 2 | 入力を「リンク投入」中心に再設計（§3） | 最終ゴールの確定 |
| 3 | Final Gatesに SC01（ショートコード構造）/ 重大度REVIEW / claim同期チェックを追加（FONT_VALIDはv2改訂時に追加済み） | E2E実測で実際に踏んだ欠陥から |
| 4 | お手本記事スタイルガイド（§14）を新設 | 「ルール数値は満たすが、お手本と違う」という指摘への対応 |
| 5 | Notion接続の実情を反映（§2）。ルール原典ページは**未アクセス** | 接続WSは個人スペースで、ルールページは404 |

## 1. 確定済みHard Rule（変更なし・再掲）

出典は3系統。優先順位は「クライアント原典 > 支給資料 > 実記事からの抽出」。

### 1.1 クライアント要件（v1でのNotion転記＋ユーザー確定4事項）

```
記事タイトル：26〜28文字（NFC正規化後）。「ベトナム」+象徴キーワード必須。3案以上生成
本文：1,500文字程度（±15%）。H2複数、各H2にSEOキーワード
メタディスクリプション：80〜90文字
図表：2枚程度/記事。支給pptxテンプレート準拠、pptx形式で納品
公開設定：全体の約2/3を公開（60〜70%）、残りを無料会員限定
サムネイル：1記事1枚。Canvaの3パターン（TYPE A/B/C）を記事ごとに交互使用。
            デザイン変更不可、文字と色味のみ変更
ブランド表記：「InfoBank」に統一（InfoBase・小文字Infobankの混入はBRAND_NAME_CONFLICT）
主情報源：NNA
Magnific：画像高解像度化が主用途。AI画像を生成する場合はprovider=Magnificに限定
納品：テスト=Notion／本番=WordPress
```

### 1.2 図表テンプレートのHard Rule（支給pptx スライド31）

```
キーメッセージ：28文字以内（黒・太字・上段）
図表タイトル：1行以内（青 #004CA0・キーメッセージの下）
フォント：Meiryo UI（生成物のXMLで latin/ea/cs 3系統に明示指定し機械検証する）
文字サイズ（タイトル以外）：14pt
出所：左下。引用4パターン（§16）
InfoBankロゴ：右下（実ロゴ画像 assets/infobank_logo/ を使用。描き起こし禁止）
```

### 1.3 会員限定ショートコード（支給PDF）

```
投稿を「制限付き」に設定
[content_control logged_in="true"] 〜 [/content_control] の直後に [member_cta_buttons]
挿入はPythonが行う。LLMに書かせない
```

## 2. Rule Freeze（Phase 0 **完了**・2026-08-20）

ルール原典「**記事作成のご案内**」を取得し凍結した。

- 取得元：`https://app.notion.com/p/3b9e27bff22b80558d08d2b78c7b8f77`
- 取得方法：Notion MCP（`notion-fetch`）は **404**（接続ワークスペース「KKIXさんのスペース」に
  当該ページが存在しないため）。ページが **Web公開共有** されていたため、
  Notionの公開API `POST /api/v3/loadPageChunk` から取得した
- 保存：`config/rules_source.md`（原文）／`config/rules.json`（構造化＋SHA-256）

**照合結果：これまで暫定Hard Ruleとしてきた10項目はすべて原典と一致**した
（タイトル26〜28字＋「ベトナム」必須／本文1,500字程度／メタ80〜90字／図表2枚・pptx納品／
公開2/3・会員1/3／サムネ1枚・3パターン交互／H2複数＋SEOキーワード／テスト=Notion納品／
現地メディア画像は出所必須／人間の目視チェック必須）。

原典で**新たに判明した要件**：

| 要件 | 原典の記述 | 対応 |
|---|---|---|
| **＋αの背景・経緯** | 「SEO重視の観点から、記事自体の内容＋αの内容があると良い」（例：これまでのベトナム展開状況のまとめ、法律なら背景・課題） | 記事の必須要素として§14へ追加。E2E記事には反映済み |
| 稼働前提 | 月30〜50記事、1記事20〜30分（慣れた前提） | 自動化の目標値。§39コスト制御の基準にする |
| WordPress入稿の作業範囲 | サムネイル作成と設定／文章の転記／画像の転記＋キャプション差し込み／カテゴリー設定／タグ設定 | 本番フェーズの`delivery/wordpress.py`の実装範囲 |
| 推奨プロンプト | 原典に要約・リストアップ用と記事作成用のプロンプトが記載 | Researcher/Writerのプロンプト設計に取り込む |

**要確認（UNKNOWN_REQUIREMENT）**：原典はMagnificを「画像サイト」とだけ記述し、
**AI画像生成の是非には触れていない**。設計書§16の「AI画像を生成するならprovider=Magnific」は
妥当だが、報道記事でAI生成画像を使うかどうかは編集方針として要確認。

以後、原典の`sha256`が変わったら **RULE_CHANGE_DETECTED として停止**し、差分を人間に提示する。

## 3. 入力（リンク投入）の設計

```
NotionキューDB「記事制作キュー」
  ├ URL          … NNA記事リンク（必須）
  ├ 本文貼付     … NNA本文（任意。§3.1の判断で必須になる）
  ├ ステータス   … NEW / RESEARCHING / REVIEW / APPROVED / ERROR（workerのSTATESに合わせ RESEARCHING。v2 §37の「RESEARCH」はこれに読み替える）
  ├ パターン     … サムネのTYPE（自動でローテーション割当）
  └ 納品ページ   … 完成した記事ページへのリンク（システムが書き込む）
```

### 3.1 NNA本文の取り扱い（権利上の段階制）

| 段階 | 挙動 | 前提 |
|---|---|---|
| 現在 | リンクから**公開部分（見出し・リード）のみ**自動取得。全文は人間が「本文貼付」へ貼る | NNA二次利用の契約確認が未了のため |
| 確認後 | 支給NNAアカウントでの全文取得を実装（保存はジョブ内限り・再配布しない） | クライアントが契約上の可否を確認できた場合のみ |

NNAへの自動ログインコードは権利確認が取れるまで書かない（v1原則の維持）。
リンク先が404・非NNAドメイン・重複URLの場合は `SOURCE_UNAVAILABLE` で停止
（発生状態: SOURCE_LOADED判定時／復帰: 人間がURLを修正するまで停止／リトライ0。
v2 §34の対応表にこのコードと `NOT_IMPLEMENTED` を追加して読む。
`worker/state.py` の FAILURES を§34の全コードへ揃える改修は Phase 3 のタスク＝未実装）。

## 4. アーキテクチャ（全体像）

```
Notion キューDB（リンク投入）
      │ ポーリング（VPS worker。※Notionポーリングは未実装＝現状ローカルキューのみ／開発時はClaude Code）
      ▼
source_loader ── NNA公開部分＋貼付本文 → source.txt
      ▼
SOURCE ANALYST ── claim分解 → claims.json
      ▼
RESEARCH FACTORY（並列3系統・Writerと完全分離）
  Primary(IR・政府) / Independent(報道・現地語) / Macro(統計・政策)
      ▼
EVIDENCE COMPILER ── evidence.json（URL・公表日・原文quote・lang・信頼度）
      ▼                    │ CONFLICT → 停止（多数決禁止）
WRITER（evidence.jsonのみ参照。Web検索権限なし）
      ▼
draft.txt（@T@タイトル5案/@M@メタ/@H@/@F@公開/@X@会員/@G@図表）
      ▼
記事系ゲート（T/M/B/F/G/SC ＋ claim同期）─ BLOCK → Writerへ差し戻し
      ▼
VISUAL FACTORY
  図表: make_figures.py（支給pptxテンプレ+replace_data+Meiryo UI強制+14pt）
  サムネ: make_thumbnail.py（TYPE A/B/Cローテーション・実ロゴ・背景はMagnific/仮画像）
      ▼
RENDER QA（LibreOffice→PNG→目視QA）→ article_proof.pdf（人間レビュー用）
      ▼
FINAL GATES 一括実行（final_gate.py・全22項目）─ BLOCK → 該当工程へ差し戻し
      ▼                                        REVIEW → 記録して続行
DELIVERY
  テスト: Notionページ作成（本文+図表画像+ファクトチェック表+ゲート結果）
  本番:   WordPress下書き（ショートコード込み）
      ▼
READY_FOR_HUMAN_REVIEW（ここで必ず停止）→ 人間承認 → APPROVED
```

## 5〜13. パイプライン各工程の仕様

v2.0の §5〜§13（Rule Versioning／Subagent構成／調査と執筆の分離／Deep Research構成／
Evidence Ledger／Double Fact Check／Claim Audit／タイトルvalidator）は**そのまま有効**。
本書では重複記載せず、v2.0を参照のこと。E2Eで実証済みの追加仕様のみ以下に記す。

- **claims.json と draft.txt の同期検査**（`check_claim_sync.py`）：記事を修正したのに
  claimを直し忘れる事故が実際に起きたため、機械検出を必須工程にする
- **CONFLICTの解消方法**：AIが多数決で決めず、(a)争点を含む文の削除、(b)出典の主語に
  合わせた表現修正、(c)人間へのエスカレーション、のいずれかを記録付きで行う
- **Evidence判定の運用実績**：VERIFIED=一次1件 or 独立2件一致／PARTIAL=単一二次のみ・
  基準日差異あり／PARTIALの数値・日付・予測は FC03(REVIEW) として人間レビューに必ず提示

## 14. お手本記事スタイルガイド（新設）

数値ルールを満たしても「お手本と違う」記事は不合格。infobank-vn.com の実記事8本から
抽出したスタイルガイド（`config/style_guide.md`・**作成済み**）に従う。

抽出・維持のプロセス：
1. 実記事5本以上からタイトル構文・リード・見出し・文体・図表位置・会員境界・締めの型を抽出
2. Writerのプロンプトに全文埋め込み（要約しない）
3. 人間修正のdiffを蓄積し、頻出修正をスタイルガイドへ昇格（1回の修正では変えない）

## 15〜17. Visual Factory仕様（E2E実証済み）

### 15. 図表（make_figures.py）
- 支給pptxのネイティブグラフを `replace_data()` で流用。PNG貼付にしない
- **フォントは自動継承されない**（実測）。latin/ea/cs 3系統へ Meiryo UI を明示指定し、
  生成物XMLのtypefaceを数えて FONT_VALID で機械検証
- 軸ラベルは規定14ptへ強制（24ptのままだとレンダラーがラベルを間引く事故が実際に発生）
- `c:tickLblSkip=1` で項目ラベルの間引きを禁止
- テンプレートregistry（`templates/template_registry.json`）でスライド番号を管理し、133枚を毎回読まない
- **留保**：render QAは Meiryo UI が無い環境では Noto Sans CJK JP 代替描画。
  実機PowerPointでの最終見た目は人間レビュー項目（E2Eレポートの留保を引き継ぐ）

### 16. 引用4パターン（支給pptx スライド32・34〜36）
DIRECT_IMAGE／DIRECT_CHART（キャプション+引用元+リンク）、INFOBANK_ORIGINAL
（出所：InfoBank作成+右下ロゴ）、INFOBANK_DERIVED（出所：〜をもとにInfoBank作成+元リンク）。
図表生成前に人間が確定（自動判定禁止）。

### 17. サムネイル（make_thumbnail.py）
- 1記事1枚。TYPE A（ニュース経済型）/B（企業ESG型）/C（解説型）を記事ごとにローテーション。
  直近記事とパターンが重複しないことをvalidatorで検証
- ロゴは `assets/infobank_logo/`（支給pptxから抽出した実ロゴ）。**描き起こし禁止**
- 文字はPython/PILで決定論的に描画（枠に収まるまで自動縮小）。生成AIに文字を描かせない
- 背景写真：Magnific接続後はMagnific生成/高解像度化。それまでは仮画像+メタデータに明記
- ブランドブルー #004CA0（実ロゴから採取。図表タイトル色と同一）

## 18. Final Gates（final_gate.py＝22項目を機械化。ただし§32全ゲートの機械化ではない）

`samples/2026-08-18_abcmart/final_gate.py` が現物。重大度3種：
- **BLOCK**：1件でもあれば READY_FOR_HUMAN_REVIEW へ進めない
- **REVIEW**：工程は止めないが、人間レビューへ必ず提示（例：FC03 Double Check未充足）
- **STUB**：外部未接続をスタブで代替した印（テストモード規定。本番では実接続に置換）

v2 §32のHard Gateとの対応（正直な実装状態）：

| v2 §32ゲート | final_gate.py | 状態 |
|---|---|---|
| ARTICLE_TITLE/META/BODY/H2/FIGURE_COUNT/FREE_RATIO | T01-03/M01/B01-03/F01/G01 | 機械化済み |
| FIGURE_KEY_MESSAGE/FIGURE_TITLE_ONE_LINE/FONT/BRAND/CITATION | F02/F03a/FONT01/BRAND01/CIT01 | 機械化済み（F03aは一次判定のみ） |
| THUMBNAIL_VALID/LOGO_VALID | TH01/TH02 | 機械化済み。**ローテーション検証は未実装** |
| ZERO_UNSUPPORTED_CLAIMS/ZERO_SOURCE_CONFLICT | FC01/FC02 | 機械化済み |
| RULE_HASH_VALID/IMAGE_PROVIDER_VALID | RULE01/IMG01 | STUB（外部未接続） |
| （§32一覧外）ショートコード構造 | SC01 | 機械化済み |
| SOURCE_AVAILABLE/RESEARCH_COMPLETE | — | workerの状態遷移で担保（final_gate.py外） |
| PPTX_VALID | — | pptxスキル validate.py で**手動実行**（E2Eで実施） |
| VISUAL_QA_VALID | — | render→PNG→**目視QA**（E2Eで実施。自動化はPhase 6） |

注意：final_gate.py は現サンプル向け実装。B03のSEOキーワードはハードコードであり、
**記事ごとのキーワードをどこで定義するか（claim/Evidenceからの導出ルール）は未定義**。
汎用化（src/validators/への移植）とあわせて Phase 3 のタスク。

## 19. 納品（テスト=Notion）

Notionページ構成（1記事=1ページ）：
```
📄 [記事タイトル]
  ├ プロパティ：ステータス／公開日予定／サムネパターン／ゲート結果サマリ
  ├ サムネイル画像
  ├ メタディスクリプション（callout）
  ├ 本文（H2見出し・図表画像を本文中に配置）
  ├ ---「ここから会員限定」divider + ショートコード原文（code block）---
  ├ 会員限定本文
  ├ toggle: タイトル5案（文字数付き）
  ├ toggle: Final Gates結果表
  ├ toggle: ファクトチェック表（claim×判定×出典URL）
  └ toggle: 人間レビュー必須項目（Double Check未充足など）
```
図表はPNGを添付し、pptx原本もファイル添付。WordPress入稿用テキスト（cms_output.txt）を
code blockで併載（コピペで入稿可能に）。

### 19.1 納品運用（今回確定）

- **納品先**：接続済みワークスペース（現状「KKIXさんのスペース」）に親ページ
  **「InfoBank記事制作」**を作り、その配下に「納品記事」「制作キュー」を置く。
  database_id は `worker.env` の `NOTION_QUEUE_DB_ID` に保存
- **再納品**：同一ページを更新する（新規ページを作らない）。旧版は削除せず、
  ページ末尾の toggle「旧版アーカイブ」へ退避して版管理する
- **ERROR時**：キューのステータス=ERROR＋「エラー詳細」プロパティへ失敗コード、
  ページ本文冒頭のcalloutに原因・再開手順を書く（人間が見て動けるように）
- **並行処理**：当面 **1ジョブ直列**。サムネのパターンローテーションが処理順に依存するため。
  「直近記事」の定義＝キューDBで直前に APPROVED/REVIEW になった記事のパターン
  （ERROR記事は飛ばす）。ローテーション状態の正はキューDBの「パターン」列。
  **ローテーションvalidatorは未実装**（Phase 4タスク）

## 20〜44.（v2.0から変更のない章）

Secrets管理／コスト制御／修正学習／VPS常駐worker／状態機械／失敗コード対応表／
Canvaプラン制限とフォールバック／Magnific実装注意点は v2.0 §17〜§40 のとおり。
状態名は `worker/state.py` と同一（IMAGE_READY/THUMBNAIL_READY）。

## 45. 実装済み資産の棚卸し（2026-08-19時点）

| 資産 | 場所 | 状態 |
|---|---|---|
| 設計書v2.0（詳細仕様） | `docs/infobank-article-factory-v2.md` | レビュー反映済み |
| レビュー報告＋対応状況 | `docs/infobank-article-factory-v2-review.md` | 完了 |
| E2E実測レポート | `samples/2026-08-18_abcmart/e2e_report.md` | 1記事完走 |
| 記事原稿＋validator | 同 `draft.txt` / `validate.py` | 全PASS |
| Final Gates統合validator | 同 `final_gate.py`（22項目） | 稼働 |
| claim分解＋Evidence Ledger | 同 `claims.json` / `evidence.json`（29claim） | 稼働 |
| claim同期チェック | 同 `check_claim_sync.py` | 稼働 |
| 図表ビルダー | 同 `make_figures.py`（フォント強制付き） | 稼働 |
| サムネ合成＋機械QA | 同 `make_thumbnail.py` / `validate_thumbnail.py` | 稼働 |
| 記事プルーフPDF生成 | 同 `make_article_pdf.py` | 稼働 |
| 実ロゴ3種 | `assets/infobank_logo/` | 抽出済み |
| テンプレートregistry | `templates/template_registry.json` | コミット済み |
| お手本スタイルガイド | `config/style_guide.md`（実記事8本から抽出） | コミット済み |
| VPS常駐worker一式 | `ai/claude/infobank-factory/` | キュー受付・重複排除・状態保存のみ実装。調査以降は`NOT_IMPLEMENTED`停止・Notionキュー連携未実装（詳細は同READMEの実装状況表）。VPS未導入 |
| 自動継続Routine | 6時間ごと新セッション起動（trig_01H3huSVgAC53nY3kWFFJXrc） | 稼働中 |

### 未完了（優先順）

1. ~~Notionルール原典の凍結~~ → **完了**（§2）
2. ~~お手本スタイルガイドの整備~~ → **完了**（`config/style_guide.md`・実記事12本から抽出）
3. Notion納品モジュール（`delivery/notion.py`）の恒久実装（今回は手動手順で1記事納品済み。手順は§19.1）
4. NNA全文自動取得の可否確認（契約）→ §3.1の段階制
5. Magnificアカウント共有→実接続
6. VPSへのworker導入（ローカル端末から `install_vps.sh` を1回実行）
7. WordPress入稿モジュール（本番フェーズ）
8. リトライ上限（同一失敗3回→人間エスカレーション）のworker実装

## 46. 移行時の読み込み順（新チャットへの指示）

```
1. AGENTS.md / CLAUDE.md（リポジトリの最上位ルール）
2. 本書 docs/infobank-article-factory-v3.md ← 唯一の上位実装仕様
3. docs/infobank-article-factory-v2.md（詳細仕様の本体。v2 §41〜§44も有効だが、
   v2 §42の「この設計書を唯一の上位実装仕様として扱う」は本書に読み替える）
4. docs/infobank-article-factory-v2-review.md（レビューと対応状況）
5. config/style_guide.md（お手本スタイル。Writerへ全文渡す）
6. samples/2026-08-18_abcmart/e2e_report.md（実測と教訓）
7. ai/claude/infobank-factory/README.md（worker実装状況表）
8. docs/ai-worklog.md（直近の進捗）

移行前チェックリスト：
- 本書・config/・templates/ がコミット＆push済みであること
- 図表生成を行う場合は、支給PPTX原本をユーザーから受領し
  templates/original_infobank.pptx へ配置してから make_figures.py を実行する
  （原本はリポジトリ非格納。templates/README.md 参照）
- 自動継続Routineのプロンプトが本書を最上位仕様として参照していること

原則：不明はUNKNOWN_REQUIREMENTで停止／未実装を成功と報告しない／
      人間レビューより先へ進まない／鍵をログに出さない
```
