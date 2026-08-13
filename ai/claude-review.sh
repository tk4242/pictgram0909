#!/usr/bin/env bash
#
# Claude Code に現在のブランチの差分を読み取り専用でレビューさせ、結果を保存する。
#
#   bash ai/claude-review.sh [base-branch]      # 既定: master
#   bash ai/claude-review.sh --uncommitted      # コミット前の変更をレビュー
#
# Claude Code は --permission-mode plan で起動し、修正を行わずに指摘だけを返す。

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if ! command -v claude >/dev/null 2>&1; then
  echo "エラー: claude コマンドが見つかりません。Claude Code を導入してから再実行してください。" >&2
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTDIR="ai/shared/reviews"
OUT="${OUTDIR}/${STAMP}_${BRANCH//\//-}_claude.md"

if [[ "${1:-}" == "--uncommitted" ]]; then
  SCOPE="コミット前の変更（staged / unstaged / untracked）"
  REVIEW_TARGET=$'次の読み取り専用コマンドで差分を確認してください。\n`git diff --no-ext-diff`\n`git diff --cached --no-ext-diff`\n`git ls-files --others --exclude-standard`'
else
  BASE="${1:-master}"
  if ! git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null; then
    echo "エラー: 比較元のブランチまたはコミットが見つかりません: ${BASE}" >&2
    exit 1
  fi
  SCOPE="${BASE} との差分"
  REVIEW_TARGET="読み取り専用コマンド \`git diff --no-ext-diff ${BASE}...HEAD\` で差分をすべて確認してください。"
fi

read -r -d '' PROMPT <<INSTRUCTIONS || true
このリポジトリは Codex と Claude Code の 2 つの AI が同じファイルを触る前提で運用しています。
まず AGENTS.md と docs/ai-worklog.md を読み、そのうえで ${SCOPE} をレビューしてください。

【対象の確認方法】
${REVIEW_TARGET}

コードやドキュメントを編集せず、
ファイルの作成・削除・git の状態変更・ネットワーク操作も行わないでください。

【チェック項目】AGENTS.md §7 のチェックリストを 1 項目ずつ確認してください。
- binding.pry / debugger / デバッグ用 puts が残っていないか
- テストが変更に追随しているか（新しい分岐にテストがあるか）
- ルーティングヘルパー名が config/routes.rb の定義と一致しているか
- Strong Parameters を通しているか（params[:user][:x] 直読みでないか）
- db/schema.rb とマイグレーションの整合が取れているか
- Codex が「検証済み」と主張している内容が、実際に実行可能なものだったか

【報告の形式】
- 確認できた項目
- 問題が見つかった項目（ファイル名と行番号つき、なぜ問題かを具体的に）
- 確認できなかった項目（理由つき）

「LGTM」だけの回答は禁止です。何を見て問題なしと判断したかを書いてください。
Codex の報告を鵜呑みにせず、自分で確かめてください。この段階では修正を提案するだけにしてください。
INSTRUCTIONS

mkdir -p "${OUTDIR}"

{
  echo "# Claude Code レビュー: ${BRANCH}"
  echo
  echo "- 日時: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "- 対象: ${SCOPE}"
  echo "- HEAD: $(git rev-parse --short HEAD)"
  echo
  echo '---'
  echo
} > "${OUT}"

echo "Claude Code に読み取り専用レビューを依頼しています（${SCOPE}）..."
claude -p --no-session-persistence --permission-mode plan \
  --disallowedTools "Edit,Write,NotebookEdit" \
  -- "${PROMPT}" 2>&1 | tee -a "${OUT}"

cat <<MSG

--------------------------------------------------------------------
保存しました: ${OUT}

次にやること:
1. 指摘内容を確認する
2. docs/ai-worklog.md に「Claude Code がレビューし、何を指摘したか」を追記する
   （AGENTS.md §8 の書式。書かないと Codex に伝わりません）
3. 指摘への対応は Codex に依頼する
--------------------------------------------------------------------
MSG
