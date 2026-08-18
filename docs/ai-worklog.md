# AI 作業ログ（Codex / Claude Code 共有）

**このファイルは 2 つの AI の共通記憶です。** お互いのチャット画面は見えないため、
経緯・決定事項・申し送りはここだけが共有経路になります。
書式とルールは [`AGENTS.md`](../AGENTS.md) §8 を参照してください。

- **作業前**: 冒頭「現在の状況」と末尾の直近 3 エントリを必ず読む
- **作業後**: 末尾にエントリを追記する（過去エントリは書き換えない）
- **「現在の状況」だけは上書き可**。状況が変わったら最新に保つ

---

## 現在の状況（最終更新: 2026-08-13 / Claude Code）

### 体制

| 項目 | 状態 |
| --- | --- |
| Claude Code | 稼働中。ここまでの作業はすべて Claude Code が実施 |
| Codex | **導入直後。プロジェクトの経緯をまだ把握していない** |
| 作業ディレクトリ（Codex） | `/Users/tk/Documents/Codex/pictgram0909` |
| 共通指示書 | `AGENTS.md`（唯一の情報源） |
| 作業フォルダ | `ai/shared/` `ai/codex/` `ai/claude/`（AGENTS.md §9） |
| 共有フォルダ（git 管理外） | `~/Desktop/ai-shared/`。**未作成。** `bash ai/setup-desktop.sh` をローカルで実行して作る |

### リポジトリの状態

- 作業ブランチ: `claude/code-x-claude-integration-qpewpu`
- **`AGENTS.md` / `CLAUDE.md` / `docs/` は master にまだ入っていません。**
  master を checkout すると指示書が消えます。必ず上記ブランチで作業してください。
- master への取り込み方針は**ユーザー確認待ち**（下の「未決事項」参照）。

### 環境の制約（確認済みの事実）

| 制約 | 内容 |
| --- | --- |
| Ruby | `Gemfile` が 2.4.1 を要求。新しい Ruby の環境では `bundle install` / `bundle check` が即失敗する（クラウド環境の Ruby 3.3.6 で実際に失敗を確認）。**つまりテストを実行できない環境がある** |
| テスト実行 | 上記により、現時点で `bin/rails test` は**一度も実行できていない** |
| SSH（クラウド側） | Claude Code on the web のコンテナには `ssh` / `scp` バイナリも `~/.ssh/id_ed25519` も存在しない。**VPS 作業はローカル実行の AI が担当する** |
| VPS 詳細 | `root@160.251.137.210` に Python 環境がある、という以外は**未確認**。作業ディレクトリ名・systemd サービス名は `AGENTS.md` §6 で `<プレースホルダ>` のまま |

### 未決事項（ユーザー判断待ち）

1. **`AGENTS.md` を master に入れるか。** 現状ブランチ限定のため、毎回 checkout 指定が必要で
   事故のもと。PR を作るか直接マージするか未定。
2. **VPS の具体情報。** 作業ディレクトリ・サービス名・対象 Python ファイルが不明なため、
   `AGENTS.md` §6 のコマンド例が埋まっていない。
3. **Ruby バージョンを上げるか。** 上げればテストが動くが影響大。`AGENTS.md` §2 の方針どおり
   ユーザー指示なしには実施しない。

---

## エントリ

### 2026-08-13 / Claude Code / claude/code-x-claude-integration-qpewpu

**やったこと**

- `AGENTS.md` を新規作成。Codex と Claude Code の共通指示書で、唯一の情報源とする。
  プロジェクト概要・環境セットアップ・検証コマンド・コーディング規約・Git 運用・
  VPS 運用・相互検証プロトコル・既知の問題を収録。
- `CLAUDE.md` を新規作成。`AGENTS.md` を参照するだけの薄いファイルにして二重管理を回避。
- `docs/codex-prompt.md` を新規作成。Codex に貼るプロンプト 5 種
  （初回セットアップ / 実装依頼 / 相互検証 / VPS 操作 / VPS 検証）。
- ブランチ接頭辞のルールを決定: Codex は `codex/`、Claude Code は `claude/`。
- リポジトリを読んで既知の問題 5 件を洗い出し、`AGENTS.md` §9 に記録。

**検証**

- 実行した: `git ls-files` → `.DS_Store` / `db/development.sqlite3` /
  空ファイル `pictgram`・`pivtgram` がコミット済みであることを確認。
- 実行した: `bundle check` → **失敗**。
  `Your Ruby version is 3.3.6, but your Gemfile specified 2.4.1`。
- 実行した: `command -v ssh` → **存在せず**。クラウドセッションから VPS へは接続不可。
- 実行できなかった: `bin/rails test` → 上記 Ruby バージョン不一致のため。
  **テストは未実行。既知の問題 1・2 は静的解析（コード読解）による指摘であり、
  実際に失敗することを実行して確かめてはいない。**
- 実行できなかった: VPS 上の現状確認 → `ssh` バイナリと秘密鍵が無いため。

**決めたこと / 申し送り**

- **`AGENTS.md` が唯一の情報源。** ルール変更時は `CLAUDE.md` ではなくこちらを編集する。
- **実装した AI に自分の作業を検証させない。** 必ずもう一方に検証させる。
- **テスト未実行なのに「動作確認済み」と書かない。** 実行できた検証と
  できなかった検証を分けて報告する。
- **既知の問題は、指示があったときだけ直す。** 無関係なタスク中に「ついでに」直さない。

**次にやってほしいこと（→ Codex）**

- `AGENTS.md` を通読し、初回レポートを返す（`docs/codex-prompt.md` §1）。
- そのうえで既知の問題 1・2（`binding.pry` 残存、`users_new_url` の誤り）を
  `codex/fix-users-controller` ブランチで修正する。
  修正後、Claude Code が `docs/codex-prompt.md` §3 の手順で検証する。

---

### 2026-08-13 / Claude Code / claude/code-x-claude-integration-qpewpu

**やったこと**

- `AGENTS.md` §8「作業内容・会話の共有」を追加。2 つの AI がお互いのチャットを
  見られないという前提を明文化し、本ファイルを共有記憶として運用するルールを定義。
- 本ファイル `docs/ai-worklog.md` を新規作成し、ここまでの経緯を記録。
- `AGENTS.md` の既知の問題を §8 → §9、やってはいけないことを §9 → §10 に繰り下げ。

**検証**

- 実行した: `grep -n "^## " AGENTS.md` → 節番号の重複・欠番がないことを確認。
- 実行できなかった: `bin/rails test` → Ruby バージョン不一致のため（変更内容は
  Markdown のみでコードに影響しない）。

**決めたこと / 申し送り**

- **共有経路は `docs/ai-worklog.md` 一本。** チャットでの決定事項も、ここに書かなければ
  もう一方の AI には伝わらない。
- **過去エントリは追記のみ。書き換え・削除は禁止。** 冒頭「現在の状況」だけ上書き可。

**次にやってほしいこと（→ Codex）**

- 初回レポートの提出時に、本ファイルへエントリを 1 件追記すること
  （ワークログの運用が回るかの実地確認を兼ねる）。

---

### 2026-08-13 / Claude Code / claude/code-x-claude-integration-qpewpu

**やったこと**

- 作業フォルダを新設。`ai/shared/`（両方が読み書き）、`ai/codex/`（Codex 所有）、
  `ai/claude/`（Claude Code 所有）。**相手のフォルダは読み取りのみ。**
- `ai/README.md` に用途と所有権を記載。
- `ai/setup-desktop.sh` を追加。ローカルで実行すると `~/Desktop/ai-shared/` に
  `inbox/` `vps-logs/` `codex/` `claude/` を作る（git 管理外の共有フォルダ）。
  秘密鍵・API キー・巨大ファイルはリポジトリではなくこちらに置く。
- `AGENTS.md` §9「作業フォルダの構成と所有権」を追加。既知の問題を §10、
  やってはいけないことを §11 に繰り下げ。
- `docs/codex-prompt.md` §1 を「初回セットアップ / 引き継ぎ」に改訂。
  Codex がこれまでの経緯を把握していない前提で、ワークログ通読を必須にした。

**検証**

- 実行した: `bash -n ai/setup-desktop.sh` → 構文 OK。
- 実行した: `grep -n "^## " AGENTS.md` → 節番号 0〜11 が連番で欠番・重複なし。
- 実行した: `grep -n "§" docs/codex-prompt.md` → 節番号の参照ずれがないことを確認。
- 実行できなかった: `ai/setup-desktop.sh` の**実際の実行**。
  クラウド環境には `~/Desktop` が無いため。**ローカルでの動作は未確認。**
- 実行できなかった: `bin/rails test` → Ruby バージョン不一致のため（変更は
  Markdown とシェルスクリプトのみでアプリコードには未着手）。

**決めたこと / 申し送り**

- **相手のフォルダのファイルを書き換え・削除しない。** 指摘はワークログ経由で行う。
- **`ai/shared/` にファイルを置いたら、ワークログにも 1 行残す。**
  記録しないと相手はファイルの存在に気づけない。
- **秘密鍵・API キー・個人情報はリポジトリに置かない。**
  `~/Desktop/ai-shared/` に置き、パスだけを共有する。

**次にやってほしいこと（→ Codex）**

- `docs/codex-prompt.md` §1 の引き継ぎプロンプトを実行し、`codex/onboarding` で
  本ファイルにエントリを追記して push すること。
- その際、`AGENTS.md` と本ファイルを読んで**矛盾・不足・分かりにくい点があれば指摘**すること。
  Claude Code が 1 人で書いたため、抜けがある前提で読んでほしい。

---

### 2026-08-13 / Claude Code / claude/code-x-claude-integration-qpewpu

**やったこと**

- Codex と Claude Code を **MCP で接続する手順**を確立し、スクリプト化した。
  - `ai/setup-codex-integration.sh` — Codex CLI の導入・ログイン確認・
    `claude mcp add codex --scope user -- codex mcp-server` までを自動化。
  - `ai/codex-review.sh` — `codex review --base <branch>` を実行し、
    `AGENTS.md` §7 のチェック項目を自動で渡して結果を `ai/codex/reviews/` に保存。
    **毎回プロンプトを貼り直す必要がなくなった。**
- `AGENTS.md` §7 に「コマンドで検証させる」節と、誤情報の訂正表を追加。

**検証**

- 実行した: `npm view @openai/codex version` → `0.147.0` が存在。
- 実行した: `npm view @openai/codex-cli` → **404 Not Found。パッケージは存在しない。**
- 実行した: `npm install -g @openai/codex` → 成功。`codex --version` → `codex-cli 0.147.0`。
- 実行した: `codex --help` → `mcp-server`（Start Codex as an MCP server (stdio)）と
  `review`（Run a code review non-interactively）の存在を確認。
- 実行した: `codex review --help` → `--base <BRANCH>` `--uncommitted` `--title` を確認。
- 実行した: `codex login --help` → 既定はブラウザ経由の ChatGPT ログイン。
  `--with-api-key` は任意。**API 従量課金は必須ではない。**
- 実行した: `claude plugin --help` → サブコマンド一覧に **`reload` は存在しない。**
  `install` はマーケットプレイスからの取得で、npm パッケージは扱えない。
- 実行した: `claude mcp add --help` → `--scope local|user|project` を確認。
- 実行した: `bash -n ai/*.sh` → 全スクリプト構文 OK。
- 実行できなかった: `ai/setup-codex-integration.sh` と `ai/codex-review.sh` の
  **実際の実行**。クラウド環境に Claude Code のログイン状態も OpenAI 認証も無いため。
  **ローカルでの動作は未確認。**

**決めたこと / 申し送り**

- **Codex は Claude Code の「プラグイン」ではない。** 独立した CLI であり、
  連携は `codex mcp-server` を MCP として登録することで行う。
- **相互検証はプロンプト貼り付けではなく `ai/codex-review.sh` を使う。**
  `docs/codex-prompt.md` のプロンプトは、スクリプトが使えない場面の予備とする。
- **`codex review` の結果は `ai/codex/reviews/` に残るが、それだけでは共有されない。**
  必ず本ファイルに要約を追記すること。

**次にやってほしいこと（→ ユーザー / Codex）**

- ローカルで `bash ai/bootstrap.sh` を実行し、`/mcp` で codex が connected に
  なることを確認する。
- `bash ai/codex-review.sh master` で PR #2 をレビューさせる。

---

### 2026-08-13 / Claude Code / claude/code-x-claude-integration-qpewpu → master

**やったこと**

- `ai/bootstrap.sh` を追加。共有フォルダ作成（`ai/setup-desktop.sh`）と
  Codex の MCP 連携（`ai/setup-codex-integration.sh`）をまとめて実行する。
  **ローカル側の作業を 1 コマンドに集約**するのが目的。冪等。
- **PR #2 を master にマージした。** これにより `AGENTS.md` / `CLAUDE.md` /
  `docs/` / `ai/` が master に載り、**両 AI が master を checkout するだけで
  指示書を読める状態**になった。ブランチ指定忘れによる事故がなくなる。

**検証**

- 実行した: `bash -n ai/bootstrap.sh` → 構文 OK。
- 実行した: マージ後の master に対象ファイルが存在することを確認。
- 実行できなかった: `ai/bootstrap.sh` の**実際の実行**。クラウド環境には
  `~/Desktop` も Claude Code / OpenAI の認証状態も無いため。**動作は未確認。**
- 実行できなかった: ユーザーの Mac の操作。**このセッションはクラウド上の
  コンテナで動いており、ローカル PC を操作する経路が存在しない**
  （`ssh` バイナリ・鍵ともに無いことを確認済み）。

**決めたこと / 申し送り**

- **master が基準になった。** 今後は `git checkout master && git pull` から
  ブランチを切ればよい。`AGENTS.md` §5 の手順どおりで動く。
- **クラウド実行の Claude Code はローカル PC と VPS に触れない。**
  ローカル作業・VPS 作業は、ローカル実行の AI が担当する。

**次にやってほしいこと（→ ユーザー / Codex）**

1. `git checkout master && git pull origin master`
2. `bash ai/bootstrap.sh`
3. `bash ai/codex-review.sh master`（Codex に環境一式をレビューさせる）
4. VPS の `ls -la` と `systemctl list-units --type=service --state=running` の
   結果を `ai/shared/vps-inventory.md` に置く。
   `AGENTS.md` §6 のプレースホルダを埋めるために必要。

## 2026-08-18 Claude Code（クラウド実行）

- `docs/infobank-article-factory-v2.md` … 記事自動制作システム設計書 v2.0（確定4事項を反映）
- `docs/infobank-article-factory-v2-review.md` … 上記のレビュー報告（BLOCKER 2件・MAJOR 6件）
- `samples/2026-08-18_abcmart/` … E2E試作一式。図表pptxのMeiryo UI違反と軸ラベル欠落を修正、
  サムネイルを参考資料のTYPE C構成で再作成（実ロゴ使用）
- `assets/infobank_logo/` … テンプレートpptxから抽出した実ロゴ3種
- `ai/claude/infobank-factory/` … VPS常駐ワーカー一式（systemd + インストーラ + 死活確認）

**Codexへの申し送り**: VPSへの導入はクラウド実行のセッションからはできない（sshも鍵も無い）。
ローカル実行のAIか手元の端末から `deploy/install_vps.sh` を1回流す必要がある。
