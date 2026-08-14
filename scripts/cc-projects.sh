#!/usr/bin/env bash
#
# cc-projects.sh - 複数プロジェクトの Claude Code Remote Control を tmux で一括起動する
#
# スマホの Claude アプリ（Code タブ）に、プロジェクト名でセッションが並ぶようにする。
# Remote Control は PC 上の claude プロセスがアウトバウンド HTTPS で繋ぐ仕組みなので、
# VPS も SSH もポート開放も不要。このスクリプトはプロジェクトのある PC で実行する。
#
# 使い方:
#   ./scripts/cc-projects.sh                    # 設定ファイル or 自動検出
#   ./scripts/cc-projects.sh ~/foo ~/bar        # パスを直接指定
#   ./scripts/cc-projects.sh --worktree ~/foo   # セッションごとに git worktree を分ける
#   ./scripts/cc-projects.sh --list             # 起動中のセッションを確認
#   ./scripts/cc-projects.sh --stop             # 全部停止
#
# 設定ファイル (1 行 1 パス、# 以降はコメント):
#   ~/.config/cc-projects
#
set -euo pipefail

TMUX_SESSION="${CC_PROJECTS_TMUX_SESSION:-ccrc}"
CONFIG_FILE="${CC_PROJECTS_CONFIG:-$HOME/.config/cc-projects}"
SPAWN_MODE="same-dir"

die() { echo "error: $*" >&2; exit 1; }
info() { echo "==> $*"; }
warn() { echo "warning: $*" >&2; }

usage() {
  # 先頭のコメントブロック（2 行目以降、最初の非コメント行まで）をそのまま使う
  awk 'NR>2 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
  exit 0
}

# --- 引数 --------------------------------------------------------------------

PROJECTS=()
for arg in "$@"; do
  case "$arg" in
    -h|--help)  usage ;;
    --worktree) SPAWN_MODE="worktree" ;;
    --list)
      tmux list-windows -t "$TMUX_SESSION" -F '#W' 2>/dev/null \
        || echo "(起動中のセッションはありません)"
      exit 0
      ;;
    --stop)
      tmux kill-session -t "$TMUX_SESSION" 2>/dev/null \
        && info "停止しました: $TMUX_SESSION" \
        || echo "(起動中のセッションはありません)"
      exit 0
      ;;
    -*) die "不明なオプション: $arg (--help を参照)" ;;
    *)  PROJECTS+=("$arg") ;;
  esac
done

# --- 前提チェック ------------------------------------------------------------

command -v tmux   >/dev/null || die "tmux が見つかりません。先にインストールしてください。"
command -v claude >/dev/null || die "claude が見つかりません。Claude Code をインストールしてください。"

# Remote Control は claude.ai のログインが必須で、以下が設定されていると失敗する。
# 前回 "Authentication error" が出た場合はここが原因のことが多い。
for var in ANTHROPIC_API_KEY ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN \
           CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX \
           DISABLE_TELEMETRY DO_NOT_TRACK CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC; do
  if [ -n "${!var:-}" ]; then
    warn "$var が設定されています。Remote Control が失敗する可能性があります (unset $var)"
  fi
done

# --- 対象プロジェクトの決定 --------------------------------------------------

if [ ${#PROJECTS[@]} -eq 0 ] && [ -f "$CONFIG_FILE" ]; then
  info "設定を読み込み: $CONFIG_FILE"
  while IFS= read -r line; do
    line="${line%%#*}"                     # コメント除去
    line="$(echo "$line" | xargs 2>/dev/null || true)"  # 前後の空白除去
    [ -n "$line" ] && PROJECTS+=("${line/#\~/$HOME}")
  done < "$CONFIG_FILE"
fi

if [ ${#PROJECTS[@]} -eq 0 ]; then
  info "設定がないため ~ 直下の git リポジトリを自動検出します"
  while IFS= read -r gitdir; do
    PROJECTS+=("$(dirname "$gitdir")")
  done < <(find "$HOME" -maxdepth 3 -type d -name .git -not -path '*/node_modules/*' 2>/dev/null | sort)
fi

[ ${#PROJECTS[@]} -gt 0 ] || die "対象プロジェクトがありません。パスを指定するか $CONFIG_FILE を作成してください。"

# --- 起動 --------------------------------------------------------------------

tmux has-session -t "$TMUX_SESSION" 2>/dev/null \
  || tmux new-session -d -s "$TMUX_SESSION" -n __bootstrap__

# claude が即座に落ちてもウィンドウを残す（エラーメッセージを読めるようにする）
tmux set-option -t "$TMUX_SESSION" remain-on-exit on >/dev/null

started=0
for dir in "${PROJECTS[@]}"; do
  dir="${dir/#\~/$HOME}"

  if [ ! -d "$dir" ]; then
    warn "スキップ: $dir (ディレクトリが存在しません)"
    continue
  fi

  # tmux のウィンドウ名に使えない文字を置換し、重複時は連番を付ける
  base="$(basename "$dir")"
  name="${base//[.:]/-}"
  suffix=2
  while tmux list-windows -t "$TMUX_SESSION" -F '#W' 2>/dev/null | grep -qx "$name"; do
    if [ "$name" = "${base//[.:]/-}" ]; then
      echo "スキップ: $name (すでに起動中)"
      continue 2
    fi
    name="${base//[.:]/-}-$((suffix++))"
  done

  tmux new-window -d -t "$TMUX_SESSION" -n "$name" -c "$dir" \
    "claude remote-control --name '$name' --spawn '$SPAWN_MODE'"
  echo "起動: $name  ($dir)"
  started=$((started + 1))
done

tmux kill-window -t "$TMUX_SESSION:__bootstrap__" 2>/dev/null || true

echo
if [ "$started" -eq 0 ]; then
  info "新規に起動したセッションはありません"
else
  info "$started 件を起動しました"
fi
cat <<EOF

次にやること:
  1. スマホの Claude アプリを開き、下部の [Code] タブをタップ
  2. プロジェクト名のセッション（PC アイコン + 緑のドット）を選んで指示を出す

tmux の操作:
  tmux attach -t $TMUX_SESSION    # 画面を見る（抜けるのは Ctrl-b → d）
  $0 --list                       # 起動中の一覧
  $0 --stop                       # 全停止

セッションが出てこない場合:
  claude doctor                   # 設定の診断
  tmux attach -t $TMUX_SESSION    # 各ウィンドウのエラーを確認
EOF
