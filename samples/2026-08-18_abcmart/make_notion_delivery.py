"""Notion納品用のMarkdownを生成する（設計書v3.0 §19）。

テスト段階の納品先はNotion。Notionは「Markdownのインポート」と「ペースト」の双方で
見出し・太字・引用・コードブロック・表を解釈するため、納品物はMarkdownで作る。

テスト形式のため会員限定部分も伏せずに全文を載せる。ただし本番の切れ目が分かるよう、
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
    "1": ("【ABCマートの海外店舗数（2026年3月末時点）】",
          "（出所）エービーシー・マート「2027年2月期第1四半期決算」をもとにInfoBank作成。",
          "figure1.png"),
    "2": ("【日系専門店チェーンのベトナム店舗数】",
          "（出所）各社公式店舗一覧・公表資料をもとにInfoBank作成。"
          "ユニクロは2026年7月時点、無印良品は2026年8月時点、ABCマートは新店を含む。",
          "figure2.png"),
}


def gate_summary():
    """final_gate.py を実行し、結果表をそのまま納品物へ載せる（未実行のまま載せない）。"""
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
        rid = parts[0]
        label = parts[1].strip() if len(parts) > 1 else ""
        actual, _, expect = tail.partition("期待=")
        rows.append((mark, rid, label, actual.strip(), expect.strip()))
    return rows, p.returncode


def main():
    lines = [l for l in (HERE / "draft.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    g = lambda p: [l[len(p):] for l in lines if l.startswith(p)]
    titles, meta = g("@T@"), g("@M@")[0]
    title = titles[0]
    pub = sum(map(n, g("@F@")))
    mem = sum(map(n, g("@X@")))

    out = [f"# {title}", ""]
    out += [f"> **メタディスクリプション（{n(meta)}字）**  ", f"> {meta}", ""]
    out += ["![サムネイル](thumbnail_typeC.png)", "",
            "*サムネイル（TYPE C・1920×1080）。背景写真は仮画像、ロゴは支給テンプレートから抽出した実ロゴ。*", "",
            "---", ""]

    member_open = False
    for l in lines:
        tag, text = l[:3], l[3:]
        if tag in ("@T@", "@M@"):
            continue
        if tag == "@X@" and not member_open:
            member_open = True
            out += ["---", "",
                    "> 🔒 **ここから会員限定**（本番はこの位置にショートコードを挿入）  ",
                    "> `[content_control logged_in=\"true\"]`",
                    "", "*テスト形式のため、以下も全文を掲載しています。*", ""]
        if tag == "@H@":
            out += [f"## {text}", ""]
        elif tag in ("@F@", "@X@"):
            out += [text, ""]
        elif tag == "@G@":
            cap, src, img = FIG[text]
            out += [f"![{cap}]({img})", "", f"**{cap}**  ", f"{src}", ""]
    if member_open:
        out += ["", "> 🔒 **会員限定ここまで**  ",
                "> `[/content_control]`  ", "> `[member_cta_buttons]`", ""]

    out += ["", "---", "", "## 納品メモ（編集部確認用）", ""]
    out += [f"- 本文 **{pub + mem}字**（無料公開 {pub}字 ／ 会員限定 {mem}字・公開比率 "
            f"**{pub / (pub + mem) * 100:.1f}%**）",
            "- 図表2点は **PowerPoint形式（figures.pptx）** で納品。支給テンプレートの"
            "ネイティブグラフを流用し、フォントは Meiryo UI を明示指定",
            "- サムネイル1点（TYPE C）。3パターンを記事ごとに交互使用する運用",
            ""]

    out += ["### タイトル案（26〜28字・「ベトナム」必須）", ""]
    for i, t in enumerate(titles, 1):
        mark = "**（採用）**" if t == title else ""
        out += [f"{i}. {t}　<{n(t)}字>{mark}"]
    out += [""]

    rows, code = gate_summary()
    out += ["### 制作ルールの自動検証（Final Gates）", "",
            "| 判定 | 項目 | 実測 | 期待 |", "|---|---|---|---|"]
    for mark, rid, label, actual, expect in rows:
        out += [f"| {mark} | {rid} {label} | {actual} | {expect} |"]
    out += ["", f"※ STUB は外部サービス未接続のため代替した項目。REVIEW は工程を止めないが"
            f"承認前の目視確認が必要な項目。（終了コード {code}）", ""]

    ev = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
    claims = json.loads((HERE / "claims.json").read_text(encoding="utf-8"))
    by = {e["claim_id"]: e for e in ev}
    out += ["### ファクトチェック（全claim × 出典）", "",
            "| ID | 内容 | 判定 | 出典 |", "|---|---|---|---|"]
    for c in claims:
        e = by.get(c["claim_id"], {})
        url = e.get("source_url", "")
        src = e.get("source_name", "—")
        link = f"[{src}]({url})" if url else src
        out += [f"| {c['claim_id']} | {c['claim'][:46]} | {e.get('status','MISSING')} | {link} |"]
    weak = [e for e in ev if e["status"] == "PARTIAL"
            and next((c["claim_type"] for c in claims if c["claim_id"] == e["claim_id"]), "")
            in ("number", "date", "forecast")]
    out += ["", f"### 承認前の確認事項：裏付けが単一ソースの数値・日付（{len(weak)}件）", ""]
    for e in weak:
        out += [f"- **{e['claim_id']}**：{e['note']}"]

    path = HERE / "notion_delivery.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"生成: {path.name}（{len(out)}行）")


if __name__ == "__main__":
    main()
