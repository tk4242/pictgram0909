"""Notion納品用のコンテンツを生成する（設計書v3.0 §19）。

Notion-flavored Markdown で出力する。テスト段階の納品先はNotion。
テスト形式のため会員限定部分も伏せずに全文を載せるが、本番の切れ目が分かるよう
ペイウォールの境界とショートコードは明示する（設計書§3のHard Ruleを可視化するため）。

使い方: python3 make_notion_delivery.py
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
n = lambda s: len(unicodedata.normalize("NFC", re.sub(r"\*", "", s.strip())))

FIG = {
    "1": ("ユニクロ32店・無印良品19店に対しABCマートは5店"
          "「日系専門店チェーンのベトナム店舗数」",
          "（出所）各社公式店舗一覧・公表資料をもとにInfoBank作成。"
          "ユニクロは2026年7月時点、無印良品は2026年8月時点、ABCマートは新店を含む。"),
    "2": ("韓国317店に対しベトナムは4店、今回の開業で5店に"
          "「ABCマートの海外店舗数（2026年3月末時点）」",
          "（出所）エービーシー・マート「2027年2月期第1四半期決算」をもとにInfoBank作成。"),
}


def gate_rows():
    """final_gate.py を実行し結果をそのまま載せる（未実行のまま載せない）。"""
    p = subprocess.run([sys.executable, str(HERE / "final_gate.py")],
                       capture_output=True, text=True)
    rows = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.startswith("[") or "]" not in line:
            continue
        mark = line[1:line.index("]")].strip()
        rest = line[line.index("]") + 1:]
        head, _, tail = rest.partition("実測=")
        parts = head.split(None, 1)
        actual, _, expect = tail.partition("期待=")
        rows.append((mark, parts[0], parts[1].strip() if len(parts) > 1 else "",
                     actual.strip(), expect.strip()))
    return rows, p.returncode


def esc(s):
    """Notion記法の制御文字を無害化する（表セル内で使う）。"""
    return s.replace("|", "｜").replace("<", "＜").replace(">", "＞")


def table(headers, rows):
    out = ['<table fit-page-width="true" header-row="true">', "\t<tr>"]
    out += [f"\t\t<td>{h}</td>" for h in headers]
    out += ["\t</tr>"]
    for r in rows:
        out += ["\t<tr>"] + [f"\t\t<td>{esc(str(c))}</td>" for c in r] + ["\t</tr>"]
    out += ["</table>"]
    return out


def main():
    lines = [l for l in (HERE / "draft.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    g = lambda p: [l[len(p):] for l in lines if l.startswith(p)]
    titles, meta = g("@T@"), g("@M@")[0]
    title = titles[0]
    pub, mem = sum(map(n, g("@F@"))), sum(map(n, g("@X@")))

    # メタディスクリプションは記事の見出し・サブタイトルではなく、
    # 原典ルール「メタディスクリプションは80〜90文字で設定し、WordPressに入稿する」の
    # とおりWordPress入稿時にSEOプラグイン欄へ貼るための入稿データ。
    # 本文の直前に見出し風コールアウトとして置くと読者向けの文言と誤認されるため、
    # 他の入稿チェック項目（サムネイル・図表・カテゴリ等）と同じ「納品メモ」に集約する。
    out = ["![サムネイル（TYPE C・1920×1080）](THUMBNAIL_URL)", "", "---", ""]

    member = False
    for l in lines:
        tag, text = l[:3], l[3:]
        if tag in ("@T@", "@M@"):
            continue
        if tag == "@X@" and not member:
            member = True
            out += ["---", "",
                    '<callout icon="🔒" color="gray_bg">',
                    "\t**ここから会員限定**（本番はこの位置にショートコードを挿入）",
                    "\t`[content_control logged_in=\"true\"]`",
                    "\tテスト形式のため、以下も全文を掲載しています。",
                    "</callout>", ""]
        if tag == "@H@":
            out += [f"## {text}", ""]
        elif tag in ("@F@", "@X@"):
            out += [text, ""]
        elif tag == "@G@":
            cap, src = FIG[text]
            out += [f"![{cap}](FIGURE{text}_URL)", "", f"**{cap}**", f"{src}", ""]
    if member:
        out += ['<callout icon="🔒" color="gray_bg">',
                "\t**会員限定ここまで**",
                "\t`[/content_control]`　`[member_cta_buttons]`",
                "</callout>", ""]

    out += ["---", "", "## 納品メモ（編集部確認用）", ""]
    out += [f"- 本文 **{pub + mem}字**（無料公開 {pub}字／会員限定 {mem}字・"
            f"公開比率 **{pub / (pub + mem) * 100:.1f}%**）",
            "- 図表2点は **PowerPoint形式（figures.pptx）** で納品。支給テンプレートの"
            "ネイティブグラフを流用し、フォントは Meiryo UI を明示指定",
            "- サムネイル1点（TYPE C）。3パターンを記事ごとに交互使用する運用",
            "- **背景写真は仮画像**（Magnific未接続のため）。本番はMagnificで差し替える",
            f"- **メタディスクリプション（{n(meta)}字・WordPress入稿用。本文には掲載しない）**："
            f"「{meta}」",
            ""]

    out += ["### タイトル案（26〜28字・「ベトナム」必須）", ""]
    out += table(["#", "案", "字数"],
                 [[i, t + ("　★採用" if t == title else ""), f"{n(t)}字"]
                  for i, t in enumerate(titles, 1)])
    out += [""]

    rows, code = gate_rows()
    out += ["## 制作ルールの自動検証 {toggle=\"true\"}", ""]
    out += ["\t" + l for l in table(["判定", "ID", "項目", "実測", "期待"],
                                    [(m, r, lb, a, e) for m, r, lb, a, e in rows])]
    out += ["\tSTUB は外部サービス未接続のため代替した項目。"
            "REVIEW は工程を止めないが承認前の目視確認が必要な項目。", ""]

    ev = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
    claims = json.loads((HERE / "claims.json").read_text(encoding="utf-8"))
    by = {e["claim_id"]: e for e in ev}
    fc = []
    for c in claims:
        e = by.get(c["claim_id"], {})
        url, src = e.get("source_url", ""), e.get("source_name", "—")
        fc.append([c["claim_id"], c["claim"][:44], e.get("status", "MISSING"),
                   f"[{esc(src[:28])}]({url})" if url else esc(src)])
    out += [f'## ファクトチェック（全{len(claims)}件） {{toggle="true"}}', ""]
    out += ["\t" + l for l in table(["ID", "内容", "判定", "出典"], fc)]
    out += [""]

    weak = [e for e in ev if e["status"] == "PARTIAL"
            and next((c["claim_type"] for c in claims if c["claim_id"] == e["claim_id"]), "")
            in ("number", "date", "forecast")]
    out += [f'## 承認前の確認事項：裏付けが単一ソースの数値・日付（{len(weak)}件） {{toggle="true"}}', ""]
    out += ["\t設計書§11は「一次情報1件＋独立情報1件」または「権威ある一次資料1件」を求める。"
            "以下は未充足のため、承認前に内容を確認すること。", ""]
    for e in weak:
        out += [f"\t- **{e['claim_id']}**：{e['note']}"]
    out += [""]

    path = HERE / "notion_delivery.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"生成: {path.name}（{len(out)}行 / ゲート終了コード {code}）")


if __name__ == "__main__":
    main()
