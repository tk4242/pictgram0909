#!/usr/bin/env bash
#
# Claude Code の SessionEnd フックから呼ばれる。
# セッション終了時に、現在の作業ブランチへ commit + push する（AGENTS.md §5）。
#
# 安全装置:
#   - master/main、または detached HEAD では絶対にコミットしない
#     （AGENTS.md は master への直接コミットを禁止しているため）
#   - master への反映は引き続き PR 経由（自動マージはしない）
#   - 変更が無ければ何もしない
#   - 何が起きても exit 0（フック失敗でセッション終了を妨げない）

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$ROOT" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

LOG="ai/hooks/session.log"
mkdir -p "$(dirname "$LOG")"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

echo "---- SessionEnd ${STAMP} (branch: ${BRANCH:-unknown}) ----" >> "$LOG"

if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
  echo "[session-end] no changes to commit" >> "$LOG"
  exit 0
fi

case "$BRANCH" in
  master|main|""|HEAD)
    echo "[session-end] on ${BRANCH:-detached HEAD}; refusing to auto-commit (AGENTS.md forbids direct commits to the default branch)" >> "$LOG"
    echo "{\"systemMessage\": \"git: ${BRANCH:-detached HEAD} 上のため自動コミットしませんでした。作業用ブランチを切ってください（AGENTS.md §5）。\"}"
    exit 0
    ;;
esac

git add -A >> "$LOG" 2>&1

if git diff --cached --quiet 2>/dev/null; then
  echo "[session-end] nothing staged after add" >> "$LOG"
  exit 0
fi

COMMIT_MSG="Session end auto-commit (${BRANCH})

Automated by ai/hooks/session-end.sh at chat session end.
Review this diff before treating it as final.

Co-Authored-By: Claude Code <noreply@anthropic.com>"

if ! git commit -m "$COMMIT_MSG" >> "$LOG" 2>&1; then
  echo "[session-end] commit failed" >> "$LOG"
  echo '{"systemMessage": "git: 自動コミットに失敗しました。ai/hooks/session.log を確認してください。"}'
  exit 0
fi

if git push -u origin "$BRANCH" >> "$LOG" 2>&1; then
  echo "[session-end] pushed ${BRANCH}" >> "$LOG"
  echo "{\"systemMessage\": \"git: ${BRANCH} に自動コミット・push しました。master への反映は別途 PR で行ってください。docs/ai-worklog.md への追記も確認してください。\"}"
else
  echo "[session-end] push failed" >> "$LOG"
  echo "{\"systemMessage\": \"git: コミットはしましたが push に失敗しました。ai/hooks/session.log を確認し、手動で push してください。\"}"
fi

exit 0
