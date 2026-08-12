# poikatsu — マルチエージェント意思決定シミュレータ

ポイ活の案件処理を「発見 → 調査 → ファクトチェック → デモトライアル → 期待値評価 →
実行可否判断 → 成果確認 → 学習」の閉ループとして実装し、**実装する前に設計を検証する**ためのもの。

依存ゼロ（Python 3.11 標準ライブラリのみ）。

```bash
python3 -m poikatsu.sim.run benchmark   # 人間ラベル付き20案件で精度評価
python3 -m poikatsu.sim.run daily       # 1日100案件 × 90日の運用シミュレーション
python3 -m poikatsu.sim.run learn       # 学習則（ベイズ vs 素朴上書き）の比較
python3 -m poikatsu.sim.run all
```

設計の全体像と、シミュレーションで発見した設計バグの一覧は
[`docs/poikatsu-multiagent-simulation.md`](../docs/poikatsu-multiagent-simulation.md) を参照。

## 設計の核

**LLM は判断材料を作るだけ。実行を決めるのは Python の決定論ルールだけ。**
LLM の出力がどれだけ自信満々でも、`engine.decide()` を迂回する経路は存在しない。

```
① prefilter      Python のみ・AI呼び出しゼロ          -49.4%
② research       証拠を集める（回答させない）
③ fact check     fact_score は Python が計算
④ dry run        公開ページのみ。ログイン後は触らない
⑤ BLOCK GATES    ★ROI より前。コスト最適化に追い越させない
⑥ ROI            金額計算は完全に Python
⑦ 合議           ここで初めて LLM を呼ぶ。BLOCK は1票 veto
⑧ 決定論ルール    唯一の実行判断者
⑨ 実行キャパ制御  人間時間予算 + 1人1回 + 申込ペース上限 ← 収益の天井
⑩ verify → learn ベータ・ベイズ更新
```

## ファイル

| ファイル | 役割 |
|---------|------|
| `sim/models.py` | ドメインモデル（本番では pydantic に置換する） |
| `sim/world.py` | シミュレーション世界。人間ラベル付きベンチマーク20件 + 日次ストリーム生成 |
| `sim/engine.py` | 決定論パート。前置フィルタ / fact_score / ROI / 合議 / ルール / ペース制御 |
| `sim/agents.py` | LLM パート。MockLLM 3枚 / Deep Research / Dry Run |
| `sim/learning.py` | ベータ・ベイズ推定、モデル別スコアカード |
| `sim/run.py` | オーケストレータと3つの評価モード |

## 自動化しない領域

`app` / `survey` カテゴリ（アプリ起動・アンケート回答・広告クリック）は
**設計として自動実行しない**。全ポイントサイトの規約で自動操作が禁止されており、
発覚時は未確定ポイント全没収＋アカウント削除で他カテゴリの資産まで失う。
シミュレーション上も収益寄与が小さく、リスクに見合わない。

Dry Run も公開ページのみを対象とし、ログインが必要な導線には触れない。
観測できなかった項目は `observable=False` として扱い、**「不明」を「問題なし」に読み替えない**。

## 本番化するときに差し替える箇所

1. `agents.MockLLM` → 実 API クライアント（インターフェースはそのまま使える）
2. モデル名・無料枠 RPD → `config/models.json`（コードに定数として持たない）
3. `world.BENCHMARK` → 実案件30件に人間が正解ラベルを付けたもの
4. `world.execute()` → 実際の記帳（`actions` テーブル）
5. `agents.dry_run()` → Playwright（robots.txt 尊重・公開ページのみ）
6. `engine.PACE_LIMIT_PER_MONTH` → 実運用値（現状は推定値）
