# 設計書v2.0 レビュー報告（2026-08-18）

レビュー方法：添付PDF・PPTX（133スライド）の全文抽出照合／前回ブランチ
（`origin/claude/article-automation-info-site-3grv4v`）のv1資料・サンプル3記事との突合／
外部仕様（Notion API・Canva MCP・Magnific・Agent SDK）の公式ドキュメント実査。
サブエージェント2体（外部仕様ファクトチェック／整合性レビュー）による並列チェック。

## 1. 外部仕様ファクトチェック結果

| # | 設計書の主張 | 判定 |
|---|---|---|
| 1 | Notion Markdown取得API（`GET /v1/pages/{page_id}/markdown`） | **正確**（要 `Notion-Version: 2026-03-11`） |
| 2 | Canva Remote MCP（作成・編集・Brand Kit・PPTXエクスポート） | **部分的に正確**（下記プラン制限） |
| 3 | Magnific MCP（`https://mcp.magnific.com`）・API・Auto mode注意 | **正確** |
| 4 | Agent SDK (Python) の Subagent / Hooks | **正確** |
| 5 | Claude CodeのリモートHTTP MCP + OAuth 2.0 | **正確** |

要追記事項：

- **Canvaプラン制限（最重要）**：`get-brand-template-dataset` / autofill（§23の「可変フィールド流し込み」の実体）は **Canva Enterprise限定**。`create-design-from-brand-template` / `search-brand-templates` / `list-brand-kits` は **Pro以上**。§23の本命経路はプラン確認がPhase 0必須。Enterprise でない場合のフォールバック（デザイン複製＋`edit-design`テキスト置換）を設計に明記する。
- Notion APIレスポンスの `truncated` / `unknown_block_ids` を検査し、truncated時は失敗扱いにするガードをRule hash生成前に追加（不完全ルールのhash化防止）。
- Magnificは「プラン上unlimitedのモデルでも**MCP/API経由はクレジット消費**」。§39コスト制御に反映。
- Agent SDKではSubagentのプログラム定義（`agents`パラメータ）が公式推奨で、ファイル定義（`.claude/agents/`）と同名時はプログラム定義が優先。§35はこの優先順位を明記する。Subagentは近年デフォルトでバックグラウンド実行のため、Research→Writer→FactCheckの逐次性は明示的に順序制御する。
- Canvaのレート制限（export 20req/min等）を§39に追加。

## 2. 整合性レビュー：BLOCKER

### B-1. 会員限定比率が反転している

- v1のNotion転記（原典からの直接転記）：「**全体の約2/3を公開、残りは無料会員限定**」＝ 公開2/3・会員1/3。
- v2.0は §4「会員限定：約2/3」→ §5 `member_ratio_target: 0.6667` → §15「free≒1/3、member≒2/3」と**逆**。
- 前回サンプル3記事のvalidate.pyは全て「公開比率60〜70%」で検証しており、v1側が実装実績とも一致。
- 修正：§5を `free_ratio_target: 0.6667` に、§15を「free≒2/3、member≒1/3」に反転。→ **ユーザー確認事項①**

### B-2. 「Canva 3パターン」の解釈

- v1のNotion転記：「サムネイルは**Canvaの3パターンを交互使用。デザイン変更不可、文字と色味のみ変更**」＝ 固定テンプレート3種を記事ごとにローテーション、1記事1枚。
- v2.0は「1記事につきA/B/C 3案制作」＋「色違い3案禁止」（原典の「文字と色味のみ変更」と真逆）を採用。
- 修正案：既定を「3テンプレートのローテーション（直近記事とパターンが重ならない検証付き）」とし、1記事3案はオプションに降格。→ **ユーザー確認事項②**

## 3. 整合性レビュー：MAJOR

- **M-1. Magnificの役割**：v1転記では「magnific（画像**高解像度化**）」であり、v1は報道メディアでの生成AI画像常用を非推奨としていた。v2.0の「唯一の画像生成provider」への格上げと無条件ゲート `MAGNIFIC_USED` は、現地メディア画像転載（Notionが明示的に許可）の記事で破綻する。→ ゲートを条件付き（生成画像が存在する場合のみ provider==magnific を強制）へ。AI生成画像の採否自体を編集方針の確認事項に。
- **M-2. v1の定量要件が脱落**：本文1,500字±、メタディスクリプション80〜90字、H2見出し＋SEOキーワード、図表2枚/記事、タイトル「ベトナム」+キーワード必須、タイトル複数案生成、元記事とのn-gram重複率、WordPress入稿、ファクトチェックシート等。前回サンプルのvalidate.pyは全て実装済みで、v2.0はむしろ後退。→ v1ルール表（T/M/B/F/G体系）を§13-14へ統合。
- **M-3. NNA二次利用リスクと手動テキスト投入の設計が消滅**：v1原則「NNAへの自動ログイン・自動取得コードは書かない。入力はテキストで受け取る」を復活させ、Phase 0に権利確認を追加。
- **M-4. 納品層の欠落**：§35にWordPress/Notion納品モジュールが無い。「納品：PPTX」は図表のみの話で、記事本体はテスト=Notion／本番=WordPress（添付PDF自体がWordPress手順書）。`delivery/` を復活。
- **M-5. 状態機械の内部矛盾**：`TITLE_LENGTH_FAIL`と`TITLE_FAIL`の名称揺れ、`CITATION_VALID`・図表validator・`UNKNOWN_REQUIREMENT`に対応する失敗状態の欠落、復帰遷移とリトライ上限（v1は最大3回→人間エスカレーション）の未定義。→「状態×失敗コード×復帰先×リトライ上限」の対応表を追加。
- **M-6. `figure_title_lines == 1` は静的検証不能**：python-pptxは折返し後の行数を測れない。改行なし＋較正済みmax_charsの一次判定＋LibreOffice render QAでの最終判定の2段構えに。

## 4. 整合性レビュー：MINOR

- 引用パターンのスライド参照は「32・34〜36」が正（33は無関係のプレースホルダ）。
- InfoBank/InfoBase混在の定量：InfoBank系14回（スライド2, 4-11, 35, 36, 115。うち小文字「Infobank」2回）、InfoBase 8回（スライド31, 119-124, 129, 133）。ルール定義スライド自体が不一致で、新しい過去事例群はInfoBase優勢＝ブランド名変更の可能性。時期による使い分けの有無もPhase 0で確認。
- §31の「Claude Code Hooks」は本番実行主体がPython workerである以上「Agent SDKのhooks」と書き分ける。
- §30 Figure Schemaの `source_type` は §10 Evidenceの同名フィールドと別義。`citation_type` に改名。
- Evidence Ledgerに原文引用 `quote`・言語 `lang` を追加（ファクトチェックシートの原資）。
- §32に**テストモード規定**が無い：Notion/Magnific未接続環境ではE2Eが `RULE_HASH_VALID` / `MAGNIFIC_USED` で必ず落ちる。免除可能ゲートと免除不可ゲート（`UNSUPPORTED_CLAIM` 等）の区別を仕様化。
- 参照切れ：`docs/infobank-article-automation.md` / `docs/pipeline-design.md` は前回ブランチにのみ存在。テンプレートPPTX原本（14.7MB）の保管場所（Git LFS検討）も未定。
- 添付PDF原文④の説明文は③のコピペ（「直前に挿入」の重複）。Rule Parserに食わせる際の注意点。

## 5. この環境（クラウド）でのテスト記事作成の実行可否

| 工程 | 可否 | 備考 |
|---|---|---|
| リサーチ・Evidence・本文・validator | ○ | WebSearch＋Python |
| 図表PPTX（テンプレート流用＋replace_data） | ○ | python-pptx 1.0.2＋テンプレートregistry準備済み |
| render QA | ○ | LibreOffice導入済み |
| サムネイル | ○ | **Canva MCP接続済み・動作確認済み** |
| Magnific画像生成 | × | MCP未接続 → プレースホルダ/Canva素材で代替 |
| Notionルール取得・キュー | × | 未接続 → v1転記からrules.yamlを手作り |
| VPS（systemd worker） | × | クラウドセッションはssh不可（CLAUDE.md）→ ローカル版Claude Codeへ委譲 |
| WordPress入稿 | × | 認証情報なし → ショートコード込みテキストを成果物に |

## 6. 総括

v2.0の骨格（役割分離・Evidence Ledger・Rule Versioning・ブランド名ゲート）は強い。
急所は「Notion原典を再取得できないままv1の転記を上書き・脱落させた箇所」であり、
**B-1（比率反転）とB-2（3パターン解釈）はv2.0自身の「不明事項を推測しない」原則に
照らしてもv1転記側を暫定Hard Ruleとすべき**。修正の最小セット：

1. §4/§5/§15 の比率反転修正
2. §22 の3案解釈の降格（ローテーション既定）
3. v1ルール表の§13-14への統合
4. §35への納品層復活
5. 状態×失敗×復帰の対応表追加

---

## 対応状況（2026-08-18 追記）

BLOCKER 2件・MAJOR 6件・MINOR 8件のうち、設計書本文（`docs/infobank-article-factory-v2.md`）
へ反映済みの項目：

| 項目 | 状態 |
|---|---|
| B-1 会員限定比率反転 | 対応済み（確定事項①） |
| B-2 Canva3パターン解釈 | 対応済み（確定事項②） |
| M-1 Magnificゲート無条件化 | 対応済み（§16を条件付きゲートへ） |
| M-2 v1定量要件の脱落 | 対応済み（§13-14へrule_id体系を統合） |
| M-3 NNA権利・手動投入原則 | 対応済み（§9・§41 Phase 0） |
| M-4 納品層の欠落 | 対応済み（§35に delivery/ 復活） |
| M-5 状態機械の内部矛盾 | 対応済み（§34に対応表を追加） |
| M-6 figure_title_lines検証不能 | 対応済み（§14に2段階検証を明記） |
| m-1〜m-7 | 対応済み（スライド参照・Hooks表現・スキーマ改名・テストモード拡張・参照切れ注記） |
| m-8（PDF原文のコピペミス） | 実害なしのため対応不要と判断 |

**実装コードとの整合性チェックで新たに1件発見**：設計書§34の状態名（`MAGNIFIC_READY`/
`CANVA_3_READY`）が、実装済みの`ai/claude/infobank-factory/worker/state.py`の状態名
（`IMAGE_READY`/`THUMBNAIL_READY`）と食い違っていた。実装側に統一。

**過大な報告の訂正**：状態機械のリトライ上限（3回→人間エスカレーション）について
「`attempts`カラムで実装済み」と書いていたが、実際は全遷移で加算される総カウンタに過ぎず、
失敗種別ごとのリトライ制御ロジックはワーカーに未実装。設計書へ「未実装」と訂正して明記した。
