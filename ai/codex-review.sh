#!/usr/bin/env bash
#
# Codex に現在のブランチの差分をレビューさせ、結果をファイルに保存する。
#
#   bash ai/codex-review.sh [base-branch]      # 既定: master
#   bash ai/codex-review.sh --uncommitted      # コミット前の変更をレビュー
#
# AGENTS.md §7「AI 間の相互検証プロトコル」のチェック項目をそのまま
# Codex への指示として渡すため、毎回プロンプトを貼り直す必要がない。

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTDIR="ai/codex/reviews"
OUT="${OUTDIR}/${STAMP}_${BRANCH//\//-}.md"

if [[ "${1:-}" == "--uncommitted" ]]; then
  TARGET=(--uncommitted)
  SCOPE="コミット前の変更（staged / unstaged / untracked）"
else
  BASE="${1:-master}"
  TARGET=(--base "${BASE}")
  SCOPE="${BASE} との差分"
fi

read -r -d '' PROMPT <<'INSTRUCTIONS' || true
このリポジトリは Codex と Claude Code の 2 つの AI が同じファイルを触る前提で運用しています。
まず AGENTS.md と docs/ai-worklog.md を読み、そのうえで差分をレビューしてください。

【チェック項目】AGENTS.md §7 のチェックリストを 1 項目ずつ潰してください。
- binding.pry / debugger / デバッグ用 puts が残っていないか
- テストが変更に追随しているか（新しい分岐にテストがあるか）
- ルーティングヘルパー名が config/routes.rb の定義と一致しているか
- Strong Parameters を通しているか（params[:user][:x] 直読みでないか）
- db/schema.rb とマイグレーションの整合が取れているか
- Claude Code が「検証済み」と主張している内容が、実際に実行可能なものだったか

【報告の形式】
- 確認できた項目
- 問題が見つかった項目（ファイル名と行番号つき、なぜ問題かを具体的に）
- 確認できなかった項目（理由つき）

「LGTM」だけの回答は禁止です。何を見て問題なしと判断したのかを書いてください。
Claude Code の報告を鵜呑みにせず、自分で確かめてください。
この段階ではコードを修正せず、指摘を返すだけにしてください。
INSTRUCTIONS

mkdir -p "${OUTDIR}"

{
  echo "# Codex レビュー: ${BRANCH}"
  echo
  echo "- 日時: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "- 対象: ${SCOPE}"
  echo "- HEAD: $(git rev-parse --short HEAD)"
  echo
  echo '---'
  echo
} > "${OUT}"

echo "Codex にレビューさせています（${SCOPE}）..."
codex review "${TARGET[@]}" --title "cross-review: ${BRANCH}" "${PROMPT}" 2>&1 | tee -a "${OUT}"

cat <<MSG

--------------------------------------------------------------------
保存しました: ${OUT}

次にやること:
1. 指摘内容を確認する
2. docs/ai-worklog.md に「Codex がレビューし、何を指摘したか」を追記する
   （AGENTS.md §8 の書式。書かないと Claude Code に伝わりません）
3. 指摘への対応は Claude Code に依頼する
--------------------------------------------------------------------
MSG
