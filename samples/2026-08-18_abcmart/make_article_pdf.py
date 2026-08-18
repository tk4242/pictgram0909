"""記事をPDFで組む（校正・確認用の記事プルーフ）。

納品物そのものではなく、人間の最終レビュー（設計書§42-24）のための一覧性のある形。
本文・タイトル・メタ・サムネイル・図表・会員限定の境界・出所・ファクトチェック結果を
1つのPDFに集約し、「ルール内に収まっているか」を紙面で確認できるようにする。

文字はすべてここで決定論的に流し込む。LLMにHTMLを書かせない。
"""
import base64
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
BRAND = "#004CA0"

n = lambda s: len(unicodedata.normalize("NFC", s.strip()))


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def load():
    lines = [l for l in (HERE / "draft.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines


def build_body(lines, fig_caption):
    """@F@/@X@/@H@/@G@ マーカーから本文HTMLを組む。会員限定の境界を紙面に明示する。"""
    html, member_open = [], False
    for l in lines:
        tag, text = l[:3], l[3:]
        if tag in ("@T@", "@M@"):
            continue
        if tag == "@X@" and not member_open:
            html.append('<div class="gate"><span>ここから会員限定</span>'
                        '<code>[content_control logged_in="true"]</code></div>')
            html.append('<div class="member">')
            member_open = True
        if tag == "@H@":
            html.append(f"<h2>{esc(text)}</h2>")
        elif tag in ("@F@", "@X@"):
            html.append(f"<p>{esc(text)}</p>")
        elif tag == "@G@":
            cap, img = fig_caption[text]
            html.append(f'<figure><img src="data:image/png;base64,{b64(HERE / img)}">'
                        f"<figcaption>{esc(cap)}</figcaption></figure>")
    if member_open:
        html.append("</div>")
        html.append('<div class="gate end"><code>[/content_control]</code>'
                    "<code>[member_cta_buttons]</code></div>")
    return "\n".join(html)


def gate_rows():
    """final_gate.py を実行し、その結果表をPDFへ埋め込む（実行せずに載せない）。"""
    proc = subprocess.run([sys.executable, str(HERE / "final_gate.py")],
                          capture_output=True, text=True)
    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        mark = line[1:line.index("]")].strip()
        rest = line[line.index("]") + 1:]
        parts = rest.split("実測=")
        left = parts[0].split(None, 1)
        rid = left[0]
        label = left[1].strip() if len(left) > 1 else ""
        actual, expect = "", ""
        if len(parts) > 1:
            ae = parts[1].split("期待=")
            actual = ae[0].strip()
            expect = ae[1].strip() if len(ae) > 1 else ""
        rows.append((mark, rid, label, actual, expect))
    return rows, proc.returncode


def main():
    lines = load()
    g = lambda p: [l[len(p):] for l in lines if l.startswith(p)]
    titles, meta = g("@T@"), g("@M@")[0]
    title = titles[4]
    pub = sum(map(n, g("@F@")))
    mem = sum(map(n, g("@X@")))

    figs = {
        "1": ("図表1：ABCマートの海外店舗数（2026年3月末時点）　"
              "出所：エービーシー・マート「2027年2月期第1四半期決算」をもとにInfoBank作成", "figure1.png"),
        "2": ("図表2：日系専門店チェーンのベトナム店舗数　"
              "出所：各社公表資料をもとにInfoBank作成", "figure2.png"),
    }
    rows, gate_code = gate_rows()

    ev_path = HERE / "evidence.json"
    if ev_path.exists():
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        claims = json.loads((HERE / "claims.json").read_text(encoding="utf-8"))
        by_id = {e["claim_id"]: e for e in ev}
        def row(c):
            e = by_id.get(c["claim_id"], {})
            st = e.get("status", "MISSING")
            return (f'<tr><td>{c["claim_id"]}</td><td>{esc(c["claim"][:52])}</td>'
                    f'<td class="s-{st}">{st}</td>'
                    f'<td>{esc(str(e.get("source_name", "—"))[:30])}</td>'
                    f'<td class="u">{esc(str(e.get("source_url", "—"))[:52])}</td></tr>')
        fc_rows = "".join(row(c) for c in claims)
        weak = [e for e in ev if e["status"] == "PARTIAL"
                and next((c["claim_type"] for c in claims if c["claim_id"] == e["claim_id"]), "")
                in ("number", "date", "forecast")]
        weak_rows = "".join(
            f'<tr><td>{e["claim_id"]}</td><td>{esc(e["note"][:150])}</td></tr>' for e in weak)
        removed = [e for e in ev if e["status"] == "RESOLVED_REMOVED"]
        rm_rows = "".join(
            f'<tr><td>{e["claim_id"]}</td><td>{esc(e["note"][:180])}</td></tr>' for e in removed)
        fc_section = f"""<h2 class="sec">ファクトチェック結果（Evidence Ledger照合・全{len(claims)}件）</h2>
        <table class="fc"><thead><tr><th>claim</th><th>内容</th><th>判定</th><th>出典</th><th>URL</th></tr></thead>
        <tbody>{fc_rows}</tbody></table>
        <h2 class="sec">人間レビュー必須：Double Check未充足（{len(weak)}件）</h2>
        <p style="font-size:8.5pt;color:#555">数値・日付・予測のclaimのうち、裏付けが単一の二次情報のみ、
        または基準日・定義に差異があるもの。設計書§11は一次1件＋独立1件、または権威ある一次資料1件を求める。
        工程は止めないが、承認前に必ず内容を確認すること。</p>
        <table><thead><tr><th>claim</th><th>内容と注意点</th></tr></thead><tbody>{weak_rows}</tbody></table>
        {'<h2 class="sec">調査で検出し記事を修正した矛盾</h2><table><thead><tr><th>claim</th><th>経緯</th></tr></thead><tbody>' + rm_rows + '</tbody></table>' if rm_rows else ''}"""
    else:
        fc_section = ('<h2 class="sec">ファクトチェック結果</h2>'
                      '<p class="warn">evidence.json が未生成のため未実施。'
                      'この状態では READY_FOR_HUMAN_REVIEW へ進めない（設計書§32）。</p>')

    gate_html = "".join(
        f'<tr class="g-{m}"><td>{m}</td><td>{r}</td><td>{esc(lb)}</td>'
        f"<td>{esc(a)}</td><td>{esc(e)}</td></tr>" for m, r, lb, a, e in rows)
    title_html = "".join(
        f'<li><span class="cnt">{n(t)}字</span>{esc(t)}'
        f'{"　<b>← 採用</b>" if t == title else ""}</li>' for t in titles)

    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>{esc(title)}</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Noto Sans CJK JP", sans-serif; color: #1a1a1a;
         font-size: 10.5pt; line-height: 1.85; margin: 0; }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline;
           border-bottom: 3px solid {BRAND}; padding-bottom: 6px; margin-bottom: 14px; }}
  .head .brand {{ color: {BRAND}; font-weight: 900; letter-spacing: .04em; }}
  .head .kind {{ font-size: 8.5pt; color: #666; }}
  h1 {{ font-size: 19pt; line-height: 1.4; margin: 0 0 4px; }}
  .meta {{ font-size: 9pt; color: #555; background: #f4f6f9; padding: 8px 11px;
           border-left: 4px solid {BRAND}; margin: 10px 0 16px; }}
  .thumb {{ width: 100%; border: 1px solid #ddd; margin-bottom: 4px; }}
  .cap {{ font-size: 8pt; color: #777; margin-bottom: 16px; }}
  h2 {{ font-size: 12.5pt; color: {BRAND}; border-left: 5px solid {BRAND};
        padding-left: 9px; margin: 22px 0 9px; }}
  h2.sec {{ color: #1a1a1a; border-left-color: #999; margin-top: 26px; }}
  p {{ margin: 0 0 11px; text-align: justify; }}
  figure {{ margin: 16px 0; page-break-inside: avoid; }}
  figure img {{ width: 100%; border: 1px solid #e0e0e0; }}
  figcaption {{ font-size: 8pt; color: #666; margin-top: 5px; }}
  .gate {{ display: flex; gap: 10px; align-items: center; margin: 20px 0 12px;
           border-top: 2px dashed {BRAND}; padding-top: 9px; }}
  .gate span {{ background: {BRAND}; color: #fff; font-size: 8.5pt;
                padding: 3px 10px; font-weight: 700; white-space: nowrap; }}
  .gate code {{ font-size: 8pt; color: #444; background: #eef1f5; padding: 3px 7px; }}
  .gate.end {{ border-top: none; border-bottom: 2px dashed {BRAND};
               padding: 0 0 9px; margin-top: 12px; }}
  .member {{ background: #fcfcfd; border-left: 3px solid #cfd8e3; padding: 2px 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 8pt; margin-top: 8px; }}
  th, td {{ border: 1px solid #dcdcdc; padding: 4px 6px; text-align: left;
            vertical-align: top; }}
  td:first-child {{ white-space: nowrap; }}
  table.fc td:nth-child(2) {{ word-break: break-word; }}
  th {{ background: #eef1f5; font-weight: 700; }}
  .g-PASS td:first-child {{ background: #e8f5e9; color: #1b5e20; font-weight: 700; }}
  .g-STUB td:first-child {{ background: #fff8e1; color: #8d6e00; font-weight: 700; }}
  .g-BLOCK td:first-child {{ background: #ffebee; color: #b71c1c; font-weight: 700; }}
  .g-REVIEW td:first-child {{ background: #e3f2fd; color: #0d47a1; font-weight: 700; }}
  .s-PARTIAL {{ background: #fff8e1; color: #8d6e00; font-weight: 700; }}
  .s-RESOLVED_REMOVED {{ background: #eceff1; color: #455a64; font-weight: 700; }}
  .s-VERIFIED {{ background: #e8f5e9; color: #1b5e20; font-weight: 700; }}
  .s-UNVERIFIED, .s-MISSING, .s-NOT_FOUND {{ background: #ffebee; color: #b71c1c; font-weight: 700; }}
  .s-PARTIAL {{ background: #fff8e1; color: #8d6e00; font-weight: 700; }}
  .s-CONFLICT {{ background: #ffebee; color: #b71c1c; font-weight: 700; }}
  td.u {{ font-size: 6.5pt; color: #666; }}
  ul.titles {{ font-size: 9pt; padding-left: 18px; }}
  ul.titles li {{ margin-bottom: 3px; }}
  .cnt {{ display: inline-block; width: 44px; color: {BRAND}; font-weight: 700; }}
  .warn {{ background: #ffebee; border-left: 4px solid #b71c1c; padding: 9px 12px;
           font-size: 9pt; color: #b71c1c; }}
  .foot {{ margin-top: 26px; border-top: 1px solid #ddd; padding-top: 8px;
           font-size: 7.5pt; color: #888; }}
  .pb {{ page-break-before: always; }}
</style></head><body>

<div class="head"><span class="brand">InfoBank</span>
  <span class="kind">記事プルーフ（人間レビュー用）　生成日: 2026-08-18</span></div>

<h1>{esc(title)}</h1>
<div class="meta"><b>メタディスクリプション（{n(meta)}字）</b><br>{esc(meta)}</div>

<img class="thumb" src="data:image/png;base64,{b64(HERE / 'thumbnail_typeC.png')}">
<div class="cap">サムネイル（TYPE C・1920×1080）。背景写真は仮画像、ロゴはテンプレートpptxから抽出した実ロゴ。</div>

{build_body(lines, figs)}

<div class="pb"></div>
<h2 class="sec">タイトル案（26〜28字・「ベトナム」必須）</h2>
<ul class="titles">{title_html}</ul>

<h2 class="sec">Final Hard Gates（設計書§32）</h2>
<table><thead><tr><th>判定</th><th>ID</th><th>項目</th><th>実測</th><th>期待</th></tr></thead>
<tbody>{gate_html}</tbody></table>
<p style="font-size:8.5pt;color:#555;margin-top:6px">
  公開 {pub}字 ／ 会員限定 {mem}字 ／ 合計 {pub + mem}字（公開比率 {pub / (pub + mem) * 100:.1f}%）。
  STUB は外部接続が無いためスタブで代替した項目（設計書§32のテストモード規定）。
</p>

{fc_section}

<div class="foot">
  本PDFは人間の最終レビュー用のプルーフ。納品物は本文テキスト（WordPress入稿用・会員限定
  ショートコード込み）と図表pptx。ゲート結果は final_gate.py の実行結果をそのまま転記している。
</div>
</body></html>"""

    html_path = HERE / "article_proof.html"
    html_path.write_text(html, encoding="utf-8")
    out = HERE / "article_proof.pdf"
    subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
                    f"--print-to-pdf={out}", "--no-pdf-header-footer",
                    html_path.as_uri()], capture_output=True, check=True)
    print(f"生成: {out.name}（ゲート終了コード {gate_code}）")


if __name__ == "__main__":
    main()
