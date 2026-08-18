#!/usr/bin/env bash
# InfoBank記事制作ワーカーを VPS へ導入する。ローカルの Claude Code / 手元の端末から実行する。
#
#   bash install_vps.sh            # VPS上で直接実行
#   ssh root@160.251.137.210 'bash -s' < install_vps.sh   # 手元から一発で流し込む
#
# 何度実行しても同じ状態になる（冪等）。既存の設定とデータは壊さない。
set -euo pipefail

APP_DIR=/opt/infobank-factory
ENV_DIR=/etc/infobank-factory
REPO_URL=https://github.com/tk4242/pictgram0909.git
BRANCH=claude/infobank-article-automation-design-9jb4hr

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

log "1/6 OSパッケージ"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# LibreOffice は図表pptxのレンダリングQA（設計書§33）に必須。
# fonts-noto-cjk は和文が豆腐にならないようにするため。
apt-get install -y -qq \
  python3 python3-venv python3-pip git curl \
  libreoffice-impress libreoffice-core \
  fonts-noto-cjk fonts-noto-cjk-extra \
  poppler-utils sqlite3

log "2/6 和文フォントの代替設定"
# Meiryo UI は proprietary で導入できない。レンダリングQAのときだけ同系統のゴシックへ寄せる。
# pptx ファイル内の指定は Meiryo UI のまま（実機PowerPointでは正しく出る）。
mkdir -p /etc/fonts/conf.d
cat > /etc/fonts/local.conf <<'FONTCONF'
<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <match target="pattern"><test name="family"><string>Meiryo UI</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Noto Sans CJK JP</string></edit></match>
  <match target="pattern"><test name="family"><string>Meiryo</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Noto Sans CJK JP</string></edit></match>
</fontconfig>
FONTCONF
fc-cache -f >/dev/null

log "3/6 リポジトリ"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

log "4/6 Python環境"
[ -d "$APP_DIR/venv" ] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet \
  claude-agent-sdk python-pptx lxml Pillow pypdfium2 requests PyYAML

log "5/6 環境変数ファイル"
mkdir -p "$ENV_DIR"
if [ ! -f "$ENV_DIR/worker.env" ]; then
  cat > "$ENV_DIR/worker.env" <<'ENVFILE'
# 値は手で入れる。このファイルをリポジトリへコミットしないこと。
ANTHROPIC_API_KEY=
NOTION_TOKEN=
NOTION_QUEUE_DB_ID=
NOTION_RULES_PAGE_ID=
MAGNIFIC_API_KEY=
CANVA_TOKEN=
# 人間レビューより先へ自動で進めない（設計書§42-24）
AUTO_APPROVE=0
POLL_INTERVAL_SEC=300
ENVFILE
  echo "  $ENV_DIR/worker.env を作成した。APIキーを記入すること。"
else
  echo "  $ENV_DIR/worker.env は既存のため触らない。"
fi
chmod 600 "$ENV_DIR/worker.env"

log "6/6 systemd"
install -m 644 "$APP_DIR/ai/claude/infobank-factory/deploy/article-worker.service" \
  /etc/systemd/system/article-worker.service
systemctl daemon-reload
systemctl enable article-worker.service
# キーが未記入のまま起動ループに入らないようにする
if grep -q '^ANTHROPIC_API_KEY=.\+' "$ENV_DIR/worker.env"; then
  systemctl restart article-worker.service
  echo "  ワーカーを起動した。"
else
  echo "  APIキーが未記入のため起動は保留。記入後に:"
  echo "    systemctl start article-worker"
fi

cat <<'DONE'

導入完了。確認コマンド:
  systemctl status article-worker
  journalctl -u article-worker -n 50 --no-pager
DONE
