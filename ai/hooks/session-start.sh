#!/usr/bin/env bash
#
# Claude Code の SessionStart フックから呼ばれる。
# セッション開始時に origin の最新を取り込む（AGENTS.md §5 の運用ルール）。
#
# 非対話・非破壊が原則:
#   - 未コミットの変更があるときは pull しない（前回セッションの作業を守る）
#   - fast-forward できないときは無理に取り込まない
#   - 何が起きても exit 0（フック失敗でセッション開始を止めない）

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$ROOT" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

LOG="ai/hooks/session.log"
mkdir -p "$(dirname "$LOG")"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

echo "---- SessionStart ${STAMP} (branch: ${BRANCH:-unknown}) ----" >> "$LOG"

if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  echo "[session-start] uncommitted changes present; skipping pull" >> "$LOG"
  echo '{"systemMessage": "git: 未コミットの変更が残っているため pull をスキップしました。内容を確認してください。"}'
  exit 0
fi

if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  echo "[session-start] detached HEAD; skipping pull" >> "$LOG"
  exit 0
fi

git fetch origin >> "$LOG" 2>&1

if git pull --ff-only origin "$BRANCH" >> "$LOG" 2>&1; then
  echo "[session-start] pulled ${BRANCH}" >> "$LOG"
  echo "{\"systemMessage\": \"git pull 完了（${BRANCH}）\"}"
else
  echo "[session-start] pull skipped (no upstream, diverged, or new branch)" >> "$LOG"
  echo '{"systemMessage": "git pull できませんでした（未 push のブランチか、履歴が分岐しています）。必要なら手動で確認してください。"}'
fi

exit 0
