#!/usr/bin/env bash
#
# デスクトップ側の AI 共有フォルダを作成する。ローカルの Mac で 1 回だけ実行する。
#
#   bash ai/setup-desktop.sh
#
# リポジトリに入れられないもの（秘密情報・巨大ファイル・VPS から取得したログ）を
# 両 AI が読み書きするための場所を用意する。git 管理外。

set -euo pipefail

ROOT="${HOME}/Desktop/ai-shared"

mkdir -p \
  "${ROOT}/inbox" \
  "${ROOT}/vps-logs" \
  "${ROOT}/codex" \
  "${ROOT}/claude"

cat > "${ROOT}/README.md" <<'MARKDOWN'
# ai-shared — AI 共有フォルダ（git 管理外）

Codex と Claude Code の両方がアクセスしてよいローカルフォルダです。
**リポジトリには入れられないもの**をここに置きます。

| ディレクトリ | 用途 | 所有者 |
| --- | --- | --- |
| `inbox/` | ユーザーが両 AI に渡すファイル | ユーザー |
| `vps-logs/` | VPS から取得したログ・設定の控え | 両方 |
| `codex/` | Codex の出力置き場 | Codex（Claude Code は読むだけ） |
| `claude/` | Claude Code の出力置き場 | Claude Code（Codex は読むだけ） |

## ルール

- **相手のフォルダのファイルを書き換え・削除しない。**
- ここに置いたことは `docs/ai-worklog.md` に 1 行記録する。
  記録しないと、もう一方の AI はファイルの存在に気づけない。
- 秘密鍵・API キーの**中身をチャットに出力しない**。パスだけを伝える。
- リポジトリにコミットしてよい内容だと判断したら、
  `ai/shared/` へ移してから commit する。

## VPS からログを取得する例

    scp -i ~/.ssh/id_ed25519 \
      root@160.251.137.210:<リモートパス> \
      ~/Desktop/ai-shared/vps-logs/
MARKDOWN

echo "作成しました: ${ROOT}"
find "${ROOT}" -maxdepth 1 -mindepth 1 | sort
