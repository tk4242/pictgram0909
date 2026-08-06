# スマホから PC のプロジェクトに指示を出す (Remote Control)

スマホの Claude アプリでプロジェクトを選んで、PC 上の Claude Code に指示を出すための手順。

## 仕組み

Remote Control は **PC 上で動く `claude` プロセス**を、スマホやブラウザから操作する機能。
コードの実行もファイルアクセスも PC 上で行われ、スマホは操作画面（リモコン）にすぎない。

- **VPS も SSH も不要**。PC からアウトバウンド HTTPS で Anthropic API に繋ぐだけ
- PC 側でインバウンドポートは開かない
- ローカルのファイル・MCP サーバー・`.env` などがそのまま使える

> スマホ側に「プロジェクト一覧」のサイドバーは存在せず、あるのは**セッション一覧**（Code タブ）。
> そのため、**プロジェクトごとに名前付きのセッションを 1 本ずつ立てる**ことで、
> 実質的にプロジェクト選択として使えるようにする。これを自動化したのが下記スクリプト。

## 前提条件

| 項目 | 内容 |
| --- | --- |
| プラン | Pro / Max / Team / Enterprise（API キー認証は不可） |
| ログイン | `claude` を起動して `/login` で claude.ai アカウントにログイン済み |
| 信頼設定 | 各プロジェクトディレクトリで一度 `claude` を起動し、workspace trust を承認済み |
| ツール | `tmux` がインストール済み |

Team / Enterprise では、Owner が管理画面で Remote Control トグルを有効にする必要がある。

## セットアップ

### 1. 対象プロジェクトを登録

`~/.config/cc-projects` に 1 行 1 パスで記述する。

```
~/pictgram0909
~/another-app
~/some-tool
```

（このファイルを作らない場合は、引数でパスを渡すか、ホーム直下の git リポジトリが自動検出される）

### 2. 起動

```bash
./scripts/cc-projects.sh
```

各プロジェクトが tmux のウィンドウとして常駐し、Remote Control セッションが立ち上がる。

### 3. スマホから接続

1. Claude アプリを開き、下部ナビの **Code** タブをタップ
2. プロジェクト名のセッション（PC アイコン + 緑のドット = オンライン）を選択
3. 指示を出す

## よく使うコマンド

```bash
./scripts/cc-projects.sh              # 起動（起動済みのものはスキップ）
./scripts/cc-projects.sh ~/foo ~/bar  # パスを直接指定して起動
./scripts/cc-projects.sh --worktree   # セッションごとに git worktree を分ける
./scripts/cc-projects.sh --list       # 起動中の一覧
./scripts/cc-projects.sh --stop       # 全停止

tmux attach -t ccrc                   # 画面を見る（抜けるのは Ctrl-b → d）
```

`--worktree` を付けると、スマホから新しいセッションを作るたびに独立した git worktree が
割り当てられ、同じプロジェクトで並行作業しても編集が衝突しない。

## 便利な設定

**スマホへのプッシュ通知** — 長いタスクの完了時や承認待ちのときに通知が届く。
PC 側で `/config` を開き、以下を有効化する。

- `Push when Claude decides`（Claude の判断で通知）
- `Push when actions required`（許可待ち・質問があるとき通知）

**毎回自動接続** — `/config` の `Enable Remote Control for all sessions` を有効にすると、
通常の `claude` 起動時も自動で Remote Control が繋がる。

## トラブルシューティング

### Authentication error が出る

Remote Control は claude.ai のログインセッションが必須で、以下の環境変数が設定されていると失敗する。

```bash
echo $ANTHROPIC_API_KEY $ANTHROPIC_BASE_URL $CLAUDE_CODE_OAUTH_TOKEN
unset ANTHROPIC_API_KEY ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN
```

`cc-projects.sh` は起動時にこれらを検出して警告を出す。

その他の確認手順:

```bash
claude doctor                    # どのチェックで落ちているか診断
claude remote-control --verbose  # 詳細なエラーを表示
claude auth login                # ログインし直す
```

`setup-token` で作った長期トークンはモデル呼び出ししかできないため、Remote Control では使えない。
`claude auth login` でフルスコープのセッショントークンを取得する必要がある。

### スマホの一覧にセッションが出てこない

```bash
tmux attach -t ccrc   # 各ウィンドウのエラーメッセージを確認
```

スクリプトは `remain-on-exit on` を設定しているため、`claude` が即座に落ちた場合も
ウィンドウが残りエラーを確認できる。

### セッションが勝手に終了する

- ターミナルや `claude` プロセスを終了するとセッションも終わる（tmux 常駐で回避）
- PC が起きているのにネット不通が **約 10 分**続くとタイムアウトして終了する。再実行が必要
- スリープや一時的なネット断は、復帰時に自動再接続される

## Remote Control と Claude Code on the web の違い

| | 実行場所 | 用途 |
| --- | --- | --- |
| Remote Control | 自分の PC | ローカルの未コミット変更・MCP・DB を使う作業を外出先から操作 |
| Claude Code on the web | Anthropic のクラウド VM | PC の電源が落ちていても OK。GitHub にプッシュ済みの内容に対する作業 |
