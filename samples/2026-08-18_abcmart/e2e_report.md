# E2E試作レポート — ABCマート ベトナム5号店（2026-08-18）

設計書：`docs/infobank-article-factory-v2.md`（Phase 7 E2E Trial相当）
実行環境：Claude Code on the web（クラウド）。Canva MCP接続済み／Magnific・Notion・VPS未接続のため
設計書§32の**テストモード規定**を適用（外部接続系ゲートのみスタブ、事実系・定量系は免除なし）。

## 成果物

| ファイル | 内容 |
|---|---|
| `draft.txt` | 記事原稿（タイトル5案・メタ・公開/会員構造マーカー付き） |
| `cms_output.txt` | WordPress入稿用テキスト（会員限定ショートコードをPythonが挿入） |
| `figures.pptx` | 図表2枚。**支給テンプレートのネイティブグラフを`replace_data`で流用**（§25-26） |
| `figure1.png` / `figure2.png` | 図表のWP貼付用PNG（LibreOffice render） |
| `thumbnail_e2e_canva.png` | サムネイル1枚（パターンB・Canva MCPで生成→編集→エクスポート） |
| `thumbnail_meta.json` | サムネイル生成メタデータ（§17相当の記録） |
| `rules_snapshot.json` | ルールスナップショット＋SHA-256（§5） |
| `validate.py` / `make_figures.py` | validator／図表ビルダー |

## Final Gates結果

| Gate | 結果 | 実測 |
|---|---|---|
| RULE_HASH_VALID | **STUB** | Notion未接続。v1転記+確定事項からスナップショット生成・hash記録 |
| SOURCE_AVAILABLE | PASS | 前回ブランチのファクトチェック済みdraftを流用 |
| ARTICLE_TITLE_VALID | PASS | 5案すべて26〜28字・「ベトナム」含有 |
| META_DESCRIPTION_VALID | PASS | 84字（80-90） |
| BODY_LENGTH_VALID | PASS | 1,625字（1,275-1,725） |
| H2_VALID | PASS | 4本・キーワード全充足 |
| FIGURE_COUNT_VALID | PASS | 2枚 |
| FREE_RATIO_VALID | PASS | 公開63.6%（60-70%） |
| FIGURE_KEY_MESSAGE_VALID | PASS | 26字／28字（≤28） |
| FIGURE_TITLE_ONE_LINE | PASS | 両図表とも改行なし＋render QA目視 |
| CITATION_VALID | PASS | 両図表ともパターン④「〜をもとにInfoBank作成」＋元資料名 |
| BRAND_VALID | PASS | InfoBankのみ。InfoBase／小文字Infobankの混入なし |
| SHORTCODE_STRUCTURE | PASS | `[content_control]`→`[/content_control]`→`[member_cta_buttons]`の順序・各1回 |
| IMAGE_PROVIDER_VALID | **STUB** | Magnificアカウント未共有（ユーザー確認済み）。Canva生成の仮画像で代替 |
| THUMBNAIL_VALID | PASS | 1枚・パターンB（ローテーション検証は前後記事がないためN/A） |
| PPTX_VALID | PASS | OOXML検証 All validations PASSED（テンプレート基準） |
| VISUAL_QA_VALID | PASS | 図表2枚：文字切れ・ロゴ欠落・出所欠落なし。サムネイル：初回にテキスト欠落を検出→Canva編集APIで修正→再QA合格 |
| ZERO_UNSUPPORTED_CLAIMS | **未実施** | Evidence Ledger／Double Fact Checkは本試作のスコープ外（Phase 2実装後に実施）。draft自体は前回制作時にファクトチェック反映済み |

## 検証できた設計上のポイント

1. **テンプレートエンジン方式（§25-27）が動く**：支給PPTXのネイティブグラフに`replace_data`でデータだけ差し替え、書式・配色・フォント・InfoBankロゴを完全保持。PNG貼り付けでなくPowerPoint chartを維持。
2. **QA→修正ループ（§33）が機能する**：サムネイル初回生成でタイトル文字欠落をVisual QAが検出し、Canvaの編集API（read-design→edit-design→commit）で修正して合格。「生成のやり直し」ではなく「決定論的な修正」で収束。
3. **ショートコードのPython挿入（§3）**：LLMに生成させず、構造化された`@F@`/`@X@`マーカーからPythonが機械的に挿入・検証。
4. **確定4事項が全て反映済み**：公開2/3（63.6%）・サムネ1枚パターンB・InfoBank統一・ABCマート題材。

## 未検証（次フェーズへ）

- Evidence Ledger／Research分離／Double Fact Check（Phase 2）— 本試作は完成済み原稿の変換ラインのみ
- Magnific実接続（アカウント共有待ち）・Notion API接続（Phase 0のルール正式取得）
- VPS常駐worker（クラウドからssh不可。ローカル版Claude Codeで実施）
- Canvaプラン確認（brand template autofillはEnterprise限定 → 現状はデザイン複製＋edit-design方式で代替可能なことを本試作で実証済み）
