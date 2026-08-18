# InfoBank記事制作ワーカー（VPS常駐）

利用者のPCの電源とは無関係に、VPS上で動き続けるための一式。
設計は [`docs/infobank-article-factory-v2.md`](../../../docs/infobank-article-factory-v2.md)。

## これは何を解決するか

Claude Code のセッションは会話が終われば止まる。記事制作を「PCを閉じても進む」状態に
するには、処理そのものをVPSの常駐プロセスへ移す必要がある。それがこのワーカー。

```
Notion / ローカルキュー
        ↓
article-worker.service（systemd・常時起動・落ちても自動復帰）
        ↓
SQLite に状態を保存（再起動しても続きから）
        ↓
READY_FOR_HUMAN_REVIEW で停止 → 人間が確認
```

## 導入（ローカル実行のClaude Code、または手元の端末から1回だけ）

クラウド実行のセッション（Claude Code on the web）には `ssh` も鍵も無いため、
この作業だけはローカルから行う（AGENTS.md §6）。

```bash
ssh root@160.251.137.210 'bash -s' < ai/claude/infobank-factory/deploy/install_vps.sh
```

その後、APIキーを記入して起動する。**キーはリポジトリに置かない。**

```bash
ssh root@160.251.137.210
vi /etc/infobank-factory/worker.env      # ANTHROPIC_API_KEY などを記入
systemctl start article-worker
```

## 日常の確認

```bash
ssh root@160.251.137.210 'bash /opt/infobank-factory/ai/claude/infobank-factory/deploy/healthcheck.sh'
```

サービスの生死・再起動回数・直近ログ・ジョブ一覧・人間レビュー待ち件数が出る。

## 更新の反映

```bash
ssh root@160.251.137.210 'bash -s' < ai/claude/infobank-factory/deploy/install_vps.sh
ssh root@160.251.137.210 'systemctl restart article-worker'
```

インストーラは冪等なので、何度流しても同じ状態になる。`worker.env` は上書きしない。

## 案件の投入

Notion連携（設計書§37）は Phase 0 で実装する。それまではローカルキューで動かす。

```
/opt/infobank-factory/ai/claude/infobank-factory/queue/<JOB_ID>.txt
  1行目 : 元記事URL
  2行目〜: 本文（人が貼る。NNAへ自動アクセスはしない）
```

同じ `source_url` は二重に処理しない（SQLiteのUNIQUE制約で担保）。

## 現在の実装状況

| 工程 | 状態 |
| --- | --- |
| キュー受付・重複排除・状態保存・再開 | 実装済み |
| ルールスナップショット | テストモードのみ（Notion未接続） |
| 元原稿の取り込み | 実装済み |
| 調査 / Evidence / Writer / FactCheck | **未実装**（Phase 2-3）→ `NOT_IMPLEMENTED` で停止する |
| 図表pptx生成・サムネイル合成・validator | `samples/2026-08-18_abcmart/` に実装済み。ワーカーへの接続は Phase 5 |

未実装の工程は成功を装わず、その場で停止して記録する。
「動いているように見えて中身が空」を避けるため。
