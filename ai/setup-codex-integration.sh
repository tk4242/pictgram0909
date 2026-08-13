#!/usr/bin/env bash
#
# Claude Code から Codex を呼べるようにする（MCP 連携）。ローカルの Mac で 1 回だけ実行する。
#
#   bash ai/setup-codex-integration.sh
#
# 検証済みの事実（codex-cli 0.147.0 / claude CLI で実際に確認）:
#   - npm パッケージ名は @openai/codex。@openai/codex-cli は存在しない（404）
#   - Codex は Claude Code の「プラグイン」ではなく、独立した CLI
#   - `claude plugin install` はマーケットプレイスからの取得で、npm パッケージは扱えない
#   - `claude plugin reload` というコマンドは存在しない
#   - 正しい連携経路は `codex mcp-server`（stdio）を Claude Code に MCP として登録すること

set -euo pipefail

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- 1. Codex CLI

say "[1/4] Codex CLI を確認"
if command -v codex >/dev/null 2>&1; then
  echo "インストール済み: $(codex --version)"
else
  echo "インストールします..."
  npm install -g @openai/codex
  echo "完了: $(codex --version)"
fi

# ------------------------------------------------------------------ 2. ログイン

say "[2/4] Codex のログイン状態を確認"
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

# ------------------------------------------------------- 3. Claude Code へ登録

say "[3/4] Claude Code に Codex を MCP サーバとして登録"
if claude mcp get codex >/dev/null 2>&1; then
  echo "登録済みです（再登録する場合は先に \`claude mcp remove codex\`）"
else
  claude mcp add codex --scope user -- codex mcp-server
  echo "登録しました"
fi

# ---------------------------------------------------------------- 4. 動作確認

say "[4/4] 動作確認"
claude mcp list

cat <<'MSG'

--------------------------------------------------------------------
セットアップ完了。

Claude Code のセッション内で `/mcp` を実行し、codex が connected に
なっていれば連携できています。

【使い方 1】Claude Code から Codex を呼ぶ
  Claude Code に「codex にこの変更をレビューさせて」と頼めば、
  MCP 経由で Codex が呼ばれます。

【使い方 2】ターミナルから直接 Codex にレビューさせる（速い）
  bash ai/codex-review.sh master

  現在のブランチと master の差分を Codex がレビューし、
  結果を ai/codex/reviews/ に保存します。
--------------------------------------------------------------------
MSG
