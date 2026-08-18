"""InfoBank記事制作ワーカー（VPS常駐）。

利用者のPCの電源とは無関係に、VPS上で systemd が起こし続ける。
落ちても Restart=always で復帰し、SQLite に残った状態から再開する。

原則:
  - 人間レビュー（READY_FOR_HUMAN_REVIEW）より先へは自動で進めない（設計書§42-24）。
  - 未実装の工程は成功を装わず NOT_IMPLEMENTED で停止して記録する。
  - 秘密情報はログに出さない。SET / UNSET だけを出す（設計書§38）。
"""
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import state

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent.parent            # /opt/infobank-factory
QUEUE_DIR = ROOT / "queue"
ARTIFACTS = ROOT / "artifacts"

SECRETS = ["ANTHROPIC_API_KEY", "NOTION_TOKEN", "MAGNIFIC_API_KEY", "CANVA_TOKEN"]

log = logging.getLogger("article-worker")

_stop = False


def _handle_signal(signum, _frame):
    """systemd stop / restart のとき、途中の工程を切らずに畳む。"""
    global _stop
    _stop = True
    log.info("シグナル %s を受信。現在の工程を終えてから停止する。", signum)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,          # journald が拾う
    )


def report_auth():
    """鍵の値は絶対に出さない。設定の有無だけを出す。"""
    for name in SECRETS:
        log.info("%s=%s", name, "SET" if os.environ.get(name) else "UNSET")


def run(cmd, cwd=None):
    """外部コマンド実行。失敗時は stderr の末尾だけを添えて例外にする。"""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
        raise RuntimeError(f"{' '.join(cmd)} が失敗: " + " / ".join(tail))
    return proc.stdout


def read_queue():
    """キューを読む。Notion未接続の間はローカルディレクトリで代替する。

    queue/<job_id>.txt に「1行目=元記事URL、2行目以降=本文」を置く。
    NNA へは自動アクセスしない（v1原則。本文は人が貼る）。
    """
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    if os.environ.get("NOTION_TOKEN"):
        # TODO(Phase 0): Notion Database をキューにする（設計書§37）。
        # 未実装のまま黙って空を返すと「案件ゼロ」と誤解されるため明示する。
        log.warning("NOTION_TOKEN はあるが Notion キュー連携は未実装。ローカルキューを見る。")
    jobs = []
    for path in sorted(QUEUE_DIR.glob("*.txt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            continue
        jobs.append((path.stem, lines[0].strip()))
    return jobs


def step(conn, job_id, source_url, current):
    """状態を1つ進める。進めた先の状態名を返す。"""
    out = ARTIFACTS / job_id
    out.mkdir(parents=True, exist_ok=True)

    if current == "NEW":
        # ルールのスナップショットとhash（設計書§5）
        if not os.environ.get("NOTION_TOKEN"):
            log.info("[%s] Notion未接続のためテストモードのルールを使う", job_id)
        return "RULES_LOADED"

    if current == "RULES_LOADED":
        src = QUEUE_DIR / f"{job_id}.txt"
        if not src.exists():
            raise FileNotFoundError(f"元原稿が見つからない: {src}")
        (out / "source.txt").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return "SOURCE_LOADED"

    if current == "SOURCE_LOADED":
        # 調査・Evidence Ledger・Writer・Fact Check は Phase 2-3 で実装する。
        # ここを「できたこと」にしてはいけない。
        raise NotImplementedError(
            "Research/Evidence/Writer/FactCheck は未実装（設計書 Phase 2-3）")

    raise NotImplementedError(f"状態 {current} の処理は未実装")


def tick(conn):
    for job_id, source_url in read_queue():
        if state.claim_new(conn, job_id, source_url):
            log.info("[%s] 受付 %s", job_id, source_url)

    for job_id, source_url, current in state.pending(conn):
        if _stop:
            return
        try:
            nxt = step(conn, job_id, source_url, current)
        except NotImplementedError as exc:
            log.warning("[%s] %s → NOT_IMPLEMENTED で停止: %s", job_id, current, exc)
            state.advance(conn, job_id, current, failure="NOT_IMPLEMENTED", detail=str(exc))
        except Exception as exc:                      # noqa: BLE001 - 落とさず記録して次へ
            log.error("[%s] %s で失敗: %s", job_id, current, exc)
            state.advance(conn, job_id, current, failure="QA_FAIL", detail=str(exc))
        else:
            log.info("[%s] %s → %s", job_id, current, nxt)
            state.advance(conn, job_id, nxt)
            if nxt == state.HUMAN_GATE:
                log.info("[%s] 人間レビュー待ち。ここから先へは自動で進めない。", job_id)


def main():
    setup_logging()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    interval = int(os.environ.get("POLL_INTERVAL_SEC", "300"))
    log.info("起動。ポーリング間隔 %d 秒", interval)
    report_auth()

    conn = state.connect()
    while not _stop:
        try:
            tick(conn)
        except Exception as exc:                       # noqa: BLE001
            log.exception("巡回で想定外の例外: %s", exc)
        # stop を取りこぼさないよう細かく刻んで待つ
        for _ in range(interval):
            if _stop:
                break
            time.sleep(1)
    log.info("停止した。")


if __name__ == "__main__":
    main()
