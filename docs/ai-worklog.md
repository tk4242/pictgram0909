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

### 2026-08-13 / Codex / codex/review-pr-2

**やったこと**

- PR #2（`claude/code-x-claude-integration-qpewpu` → `master`）について、`AGENTS.md`、
  本ワークログ、追加された `CLAUDE.md`・`ai/`・`docs/codex-prompt.md`、および
  `git diff master...HEAD` の全差分をレビューした。アプリケーションコードは変更していない。

**検証**

- 実行した: `bundle check` → 成功。`The Gemfile's dependencies are satisfied`。
- 実行した: `ruby --version` / `bundle exec ruby --version` → どちらも
  `ruby 2.4.1p111`。
- 実行した: `bin/rails routes`、`bin/rails test test/models` → どちらも失敗。
  Ruby の `digest/md5.bundle` が削除済みの
  `/usr/local/opt/openssl/lib/libcrypto.1.0.0.dylib` を要求する `LoadError` のため、
  Rails とテストランナーは起動できなかった。
- 実行した: `git diff --check master...HEAD` → 成功（空白エラーなし）。
- 実行した: `bash -n ai/setup-desktop.sh` → 成功。Claude Code の構文チェック主張は再現できた。
- 実行できなかった: `bin/rails test` → 上記 OpenSSL 共有ライブラリ欠落によりテスト開始前に失敗。

**決めたこと / 申し送り**

- **P1: §2 の環境判定は不十分。** この Mac では `bundle check` と Ruby 2.4.1 は成功する一方、
  Rails は旧 OpenSSL 1.0.0 の欠落で起動しない。Ruby のバージョン一致だけで
  「テストを実行できる」と判断せず、`bin/rails routes` など Rails 起動確認を必須にすべき。
  今回はレビューのみで `AGENTS.md` は修正していない。
- **P1: §5 と `docs/codex-prompt.md` §2 の分岐元が矛盾。** §5 は常に master から新規ブランチを
  切る一方、プロンプトはワークログ記載の現行ブランチから分岐するよう指示する。現状では
  指示書自体が master に無いため、どちらを正とするかを明文化する必要がある。
- **P1: VPS 禁止事項はコマンド名の列挙だけでは不足。** root での `sudo` 不要な
  `reboot` / `shutdown`、`mv`・リダイレクト・`truncate` による破壊的上書き、
  `chmod` / `chown`、ユーザー・SSH 鍵の変更、DB 書き込み・Docker 操作・ネットワーク設定変更が
  明示的に禁止されていない。操作の種類で禁止する必要がある。また `cat` は秘密情報を出力し得るため、
  秘密情報を含むファイルの表示禁止も必要。
- **P2: `ai/setup-desktop.sh` は既存の `~/Desktop/ai-shared/README.md` を無条件に上書きし、
  作成ディレクトリの権限を固定しない。** 秘密情報・VPS ログの置き場としては、既存ファイル保護と
  `0700` 相当の権限方針を決める必要がある。
- Claude Code の「Ruby 3.3.6 のクラウド環境では `bundle check` が失敗」「テスト未実行」という
  記録は環境を限定しており、今回のローカル結果とは矛盾しない。ただし現在の環境では別原因で
  テストが起動不能であることを本エントリで共有する。
- `AGENTS.md` / `docs/ai-worklog.md` / `docs/codex-prompt.md` に追加された § 番号参照は
  現時点の節番号と一致し、PR 差分はアプリケーションコード・テスト・ルーティング・DB スキーマを
  変更していないことを確認した。

**次にやってほしいこと**

- ユーザーの方針決定後、上記 P1/P2 を独立したドキュメント整備タスクで解消すること。
  特に master への指示書取り込み方針と、Rails 起動不能なローカル環境の扱いを先に決める。
