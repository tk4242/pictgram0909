#!/usr/bin/env bash
#
# Claude Code と Codex を相互に呼べるようにする（MCP 連携）。ローカルの Mac で 1 回だけ実行する。
#
#   bash ai/setup-codex-integration.sh
#
# 検証済みの事実（codex-cli 0.147.0 / claude CLI で実際に確認）:
#   - npm パッケージ名は @openai/codex。@openai/codex-cli は存在しない（404）
#   - Codex は Claude Code の「プラグイン」ではなく、独立した CLI
#   - `claude plugin install` はマーケットプレイスからの取得で、npm パッケージは扱えない
#   - `claude plugin reload` というコマンドは存在しない
#   - Claude Code → Codex: `codex mcp-server` を Claude Code に MCP として登録する
#   - Codex → Claude Code: `claude mcp serve` を Codex に MCP として登録する

set -euo pipefail

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- 1. Codex CLI

say "[1/5] Codex CLI を確認"
if command -v codex >/dev/null 2>&1; then
  echo "インストール済み: $(codex --version)"
else
  echo "インストールします..."
  npm install -g @openai/codex
  echo "完了: $(codex --version)"
fi

# ------------------------------------------------------------------ 2. Claude Code CLI

say "[2/5] Claude Code CLI を確認"
if command -v claude >/dev/null 2>&1; then
  echo "インストール済み: $(claude --version)"
else
  echo "Claude Code CLI が見つかりません。Claude Code を導入してから再実行してください。" >&2
  exit 1
fi

# ------------------------------------------------------------------ 3. ログイン

say "[3/5] Codex のログイン状態を確認"
if codex login status >/dev/null 2>&1; then
  codex login status
else
  cat <<'MSG'
未ログインです。次のどちらかを実行してください。

  A. ChatGPT アカウントでログイン（Plus / Pro のプランに Codex 利用が含まれます）
       codex login

  B. OpenAI API キーでログイン（API の従量課金を使う場合）
       printenv OPENAI_API_KEY | codex login --with-api-key

ログイン後、このスクリプトをもう一度実行してください。
MSG
  exit 1
fi

# ------------------------------------------------------- 4. Claude Code へ登録

say "[4/5] Claude Code に Codex を MCP サーバとして登録"
if claude mcp get codex >/dev/null 2>&1; then
  echo "登録済みです（再登録する場合は先に \`claude mcp remove codex\`）"
else
  claude mcp add codex --scope user -- codex mcp-server
  echo "登録しました"
fi

# ----------------------------------------------------------- 5. Codex へ登録

say "[5/5] Codex に Claude Code を MCP サーバとして登録"
if codex mcp get claude >/dev/null 2>&1; then
  echo "登録済みです（再登録する場合は先に \`codex mcp remove claude\`）"
else
  codex mcp add claude -- claude mcp serve
  echo "登録しました"
fi

# ---------------------------------------------------------------- 動作確認

say "登録状態を確認"
claude mcp list
codex mcp list

if claude auth status 2>/dev/null | grep -Eq '"loggedIn"[[:space:]]*:[[:space:]]*true'; then
  CLAUDE_AUTH_MESSAGE="Claude Code はログイン済みです。"
else
  CLAUDE_AUTH_MESSAGE="Claude Code は未ログインです。実レビューの前に \`claude\` を起動して \`/login\` を完了してください。"
fi

cat <<'MSG'

--------------------------------------------------------------------
セットアップ完了。

Claude Code のセッション内で `/mcp` を実行し、codex が connected に
なっていれば Claude Code → Codex の連携ができています。

Codex 側は、**新しいタスク**で Claude Code MCP を読み込みます。
現在開いている Codex タスクには設定が自動反映されないため、設定後に新規タスクを
開始してください。

【使い方 1】Claude Code から Codex を呼ぶ
  Claude Code に「codex にこの変更をレビューさせて」と頼めば、
  MCP 経由で Codex が呼ばれます。

【使い方 2】ターミナルから直接 Codex にレビューさせる（速い）
  bash ai/codex-review.sh master

  現在のブランチと master の差分を Codex が読み取り専用でレビューし、
  結果を ai/codex/reviews/ に保存します。

【使い方 3】ターミナルから直接 Claude Code にレビューさせる（速い）
  bash ai/claude-review.sh master

  現在のブランチと master の差分を Claude Code が読み取り専用でレビューし、
  結果を ai/shared/reviews/ に保存します。
--------------------------------------------------------------------
MSG

echo "${CLAUDE_AUTH_MESSAGE}"
