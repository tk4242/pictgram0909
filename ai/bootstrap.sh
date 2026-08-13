#!/usr/bin/env bash
#
# ローカル環境の初期セットアップを 1 コマンドで行う。
#
#   bash ai/bootstrap.sh
#
# 実行内容:
#   1. ~/Desktop/ai-shared/ の作成（git 管理外の共有フォルダ）
#   2. Codex CLI の導入と Claude Code への MCP 登録
#   3. 連携の動作確認
#
# 何度実行しても壊れない（冪等）。

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

say() { printf '\n\033[1m========== %s ==========\033[0m\n' "$*"; }

say "1/3 デスクトップ共有フォルダ"
bash ai/setup-desktop.sh

say "2/3 Codex 連携（MCP）"
if ! bash ai/setup-codex-integration.sh; then
  cat <<'MSG'

Codex のログインが未完了のため、ここで中断しました。
上に表示された手順でログインしてから、もう一度このスクリプトを実行してください。
MSG
  exit 1
fi

say "3/3 連携の動作確認"
if codex review --help >/dev/null 2>&1; then
  echo "OK: codex review が利用可能"
else
  echo "NG: codex review が使えません。codex --version を確認してください"
  exit 1
fi

cat <<'MSG'

--------------------------------------------------------------------
セットアップ完了。

次にやること:

  # Codex に現在のブランチをレビューさせる
  bash ai/codex-review.sh master

  # 結果は ai/codex/reviews/ に保存されます。
  # 指摘の要約を docs/ai-worklog.md に追記してください（AGENTS.md §8）。
  # 追記しないと Claude Code には伝わりません。

Claude Code のセッション内で `/mcp` を実行すると、codex が
connected になっているのを確認できます。
--------------------------------------------------------------------
MSG
