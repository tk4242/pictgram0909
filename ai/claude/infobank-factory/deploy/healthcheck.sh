#!/usr/bin/env bash
# ワーカーの生死と直近の状態を1画面で見る。VPS上で実行する。
set -uo pipefail

echo "=== service ==="
systemctl is-active article-worker >/dev/null 2>&1 \
  && echo "active" || { echo "INACTIVE"; systemctl status article-worker --no-pager | tail -5; }
systemctl show article-worker -p NRestarts --value 2>/dev/null | sed 's/^/再起動回数: /'

echo
echo "=== 直近のログ（20行） ==="
journalctl -u article-worker -n 20 --no-pager 2>/dev/null || echo "ログなし"

echo
echo "=== ジョブの状態 ==="
DB=/opt/infobank-factory/ai/claude/infobank-factory/data/jobs.sqlite3
if [ -f "$DB" ]; then
  sqlite3 -header -column "$DB" \
    "SELECT job_id, state, COALESCE(failure,'-') AS failure, attempts,
            datetime(updated_at,'unixepoch','localtime') AS updated
     FROM jobs ORDER BY updated_at DESC LIMIT 15;"
  echo
  sqlite3 "$DB" "SELECT '人間レビュー待ち: ' || COUNT(*) FROM jobs
                 WHERE state='READY_FOR_HUMAN_REVIEW';"
  sqlite3 "$DB" "SELECT '停止中(要対応): ' || COUNT(*) FROM jobs WHERE failure IS NOT NULL;"
else
  echo "DB未作成（まだ1件も処理していない）"
fi
