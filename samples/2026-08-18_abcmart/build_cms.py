"""draft.txt から WordPress入稿用テキストを生成する（設計書§3・恒久版）。

- 会員限定ショートコードはここで機械挿入する（LLMに書かせない）
- 太字マーカー **x** は <strong>x</strong> へ変換
- 図表キャプションは記事内書式「（出所）〜をもとにInfoBank作成。」（style_guide §5）
"""
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
n = lambda s: len(unicodedata.normalize("NFC", re.sub(r"\*", "", s.strip())))
strong = lambda s: re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

FIG_CAP = {
    "1": "ユニクロ32店・無印良品19店に対しABCマートは5店「日系専門店チェーンのベトナム店舗数」（出所）各社公式店舗一覧・公表資料をもとにInfoBank作成。ユニクロは2026年7月時点、無印良品は2026年8月時点、ABCマートは新店を含む。",
    "2": "韓国317店に対しベトナムは4店、今回の開業で5店に「ABCマートの海外店舗数（2026年3月末時点）」（出所）エービーシー・マート「2027年2月期第1四半期決算」をもとにInfoBank作成。",
}



def build():
    lines = [l for l in (HERE / "draft.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    g = lambda p: [l[len(p):] for l in lines if l.startswith(p)]
    titles, meta = g("@T@"), g("@M@")[0]
    out, member = [], False
    for l in lines:
        tag, text = l[:3], l[3:]
        if tag in ("@T@", "@M@"):
            continue
        if tag == "@X@" and not member:
            out.append('[content_control logged_in="true"]\n')
            member = True
        if tag == "@H@":
            out.append(f"<h2>{text}</h2>\n")
        elif tag in ("@F@", "@X@"):
            out.append(strong(text) + "\n")
        elif tag == "@G@":
            out.append(f"[図表{text}：{FIG_CAP[text]}]\n")
    out.append("[/content_control]\n")
    out.append("[member_cta_buttons]\n")
    head = (f"タイトル（採用案）: {titles[0]}\n"
            f"メタディスクリプション: {meta}\n"
            f"投稿制限: 制限付き\n\n---\n\n")
    (HERE / "cms_output.txt").write_text(head + "\n".join(out), encoding="utf-8")
    c = (HERE / "cms_output.txt").read_text(encoding="utf-8")
    assert c.count('[content_control logged_in="true"]') == 1
    assert c.count("[/content_control]") == 1
    assert c.index("[/content_control]") < c.index("[member_cta_buttons]")
    assert "**" not in c, "太字マーカーが未変換"
    print(f"cms_output.txt 生成（採用タイトル: {titles[0]} {n(titles[0])}字）")


if __name__ == "__main__":
    build()
