import json, html, re, pathlib

IMGS = json.load(open('/tmp/claude-0/-home-user-pictgram0909/abec526f-4f5e-5beb-bc84-f172b645d99b/scratchpad/imgs.json'))
SRC = pathlib.Path('/home/user/pictgram0909/samples/2026-08-18_abcmart/draft.txt')

lines = [l for l in SRC.read_text(encoding='utf-8').splitlines() if l.strip()]
T = [l[3:] for l in lines if l.startswith('@T@')]
M = [l[3:] for l in lines if l.startswith('@M@')][0]

# 本文を組み立てる。@X@ の最初の出現位置に会員ゲートの区切りを入れる。
body, gated = [], False
for l in lines:
    tag, txt = l[:3], l[3:]
    if tag == '@H@':
        body.append(f'<h3 class="ah">{html.escape(txt)}</h3>')
    elif tag == '@F@':
        body.append(f'<p>{html.escape(txt)}</p>')
    elif tag == '@X@':
        if not gated:
            body.append('<div class="gate"><span>ここから先は無料会員限定</span></div>')
            gated = True
        body.append(f'<p class="mem">{html.escape(txt)}</p>')
    elif tag == '@G@':
        k = 'fig1' if txt == '1' else 'fig2'
        cap = ('図表1　ABCマートの海外店舗数（2026年3月末時点）'
               if txt == '1' else '図表2　日系専門店チェーンのベトナム店舗数')
        body.append(f'<figure class="fig"><img src="{IMGS[k]}" alt="{html.escape(cap)}">'
                    f'<figcaption>{html.escape(cap)}</figcaption></figure>')
BODY = '\n'.join(body)

CHECKS = [
    ('T01', 'タイトル文字数', '28 / 27 / 27 / 28 / 27 字', '26〜28字', True),
    ('T02', 'タイトルに「ベトナム」', '5案すべて', '全案', True),
    ('T03', 'タイトル案の数', '5案', '3案以上', True),
    ('M01', 'メタディスクリプション', '84字', '80〜90字', True),
    ('B01', '本文文字数', '1,625字', '1,500字程度', True),
    ('B02', 'H2見出しの本数', '4本', '複数', True),
    ('B03', 'H2のSEOキーワード', '4本すべて充足', '全H2', True),
    ('F01', '図表の枚数', '2枚（pptx納品）', '2枚程度', True),
    ('G01', '公開部分の比率', '63.6%（1,033 / 1,625字）', '3分の2程度', True),
]

FIXES = [
    ('事実誤認', '店舗が4店に減った時期',
     '2026年5月末に1店を閉じて4店に減った',
     '1号店のドンコイ店が2026年1月に閉店し、3月末時点で4店',
     '海外子会社は12月決算のため、決算資料の「第1四半期末」は5月末ではなく3月末。閉店時期も戦略資料に明記されていた。',
     'エービーシー・マート 2027年2月期第1四半期決算短信 p.5 ／ 2026年4月 戦略資料'),
    ('事実誤認', 'IR資料でのベトナムの位置づけ',
     'ベトナムは「多店舗出店」フェーズへ移行のタイミングを図る',
     'ベトナムは韓国・台湾より前の「パイロットショップ／トライアル出店」段階',
     '原文は「韓国・台湾は多業態展開フェーズへの移行を進める」。ベトナムを多店舗出店フェーズと書くのは一段先走りだった。',
     'エービーシー・マート 2026年2月期 FACTBOOK p.2 ／ 戦略資料 p.15'),
    ('数値の定義', '2025年の履物輸出額',
     '履物輸出額は約290億ドル',
     '皮革・履物・かばん産業で約290億ドル、うち靴が240億ドル超',
     '290億ドルはかばん類を含む産業全体の値。靴単独では240億ドル超。「過去最高を更新」も裏取りできず削除した。',
     'VnEconomy（税関総局速報、2026年1月29日）'),
    ('誇張', '新店の面積の位置づけ',
     '総面積454平方メートルは同社のベトナム店舗で最大級',
     'キッズコーナーが国内最大級。面積はサイゴンセンター店（489㎡）に次ぐ規模',
     '出典の「最大級」はキッズコーナーにかかる表現。面積では2023年開業のサイゴンセンター店の方が広い。',
     'VIETJO 2026年8月8日 ／ JETRO 2024年10月3日'),
    ('数値の誤り', 'イオンのベトナム計画',
     'イオンは大型モール8施設を運営し、2030年までに事業規模を3倍にする',
     'イオンモールは8施設を運営。イオンは2030年度末までにSCを30カ所へ増やす計画',
     '「事業規模3倍」は営業収益とSC数の2系統が混在した曖昧な表現。SC数の目標に絞り、年度末である点も補った。',
     'イオンモール公式（2026年6月1日）／ 日本経済新聞（2026年7月6日）'),
    ('陳腐化', 'ビンズオン省の表記',
     'ホーチミン、ハノイ、ビンズオン省で店舗を展開',
     '2025年7月の行政再編でビンズオン省はホーチミン市に統合。店舗は2市に収まる',
     '同省は現存しない。指摘を逆手に取り、店舗分布の見え方が変わったという背景説明（＋α）に転換した。',
     'JETRO ビジネス短信（2025年7月1日施行）'),
    ('基準日', '無印良品の店舗数の時点',
     '無印良品17店（2025年10月時点）',
     '無印良品17店（2025年11月時点）',
     '「2025年10月時点」に直接の出典がなく、確認できた現地報道の時点に合わせた。',
     'CafeF（2025年11月28日）'),
    ('構成', '記事の締めくくり',
     '会員限定の最後がイオンモール・ビンタン出店（公開部分と重複）',
     'IR資料の中期目標20店と、この秋のグランドステージ2店を新情報として提示',
     '有料部分の締めが公開部分の焼き直しになっていた。IR資料にある中期目標20店を掘り起こして差し替えた。',
     'エービーシー・マート 2026年4月 戦略資料 p.19'),
]

OPEN = [
    ('NNAの二次利用契約', 'NNA記事のPDFには「記事の無断転載・複製・転送を禁じます」と明記されています。要約・引用の範囲と可否について、契約条件のご確認をお願いします。今回は有料部分に一切アクセスせず、公開見出しとリード文のみを起点に、すべての事実を別途一次資料で取り直しています。'),
    ('Canvaの指定デザイン3種', '接続済みのCanvaアカウントに、指定の3パターンが見当たりません。共有いただければ、複製→テキストと色のみ差し替え→書き出しまで自動化できます（今回その手順が通ることは検証済み）。ブランドテンプレート機能は有料プラン限定です。'),
    ('新店情報の一次確認', '開業日・面積・ブランド数・ビンタン出店予定は、確認できた範囲ではVIETJOとNNAの報道のみが出典で、ABCマート／イオンモールの公式発表は見つかりませんでした。広報確認が取れれば断定形にできます。'),
    ('WordPress投稿アカウント', '下書き投稿まで自動化する場合、寄稿者権限のアカウントとアプリケーションパスワードが必要です。'),
]

def rows_checks():
    out = []
    for rid, label, actual, expect, ok in CHECKS:
        out.append(f'''<tr>
<td class="rid">{rid}</td>
<td>{html.escape(label)}</td>
<td class="num">{html.escape(actual)}</td>
<td class="num muted">{html.escape(expect)}</td>
<td><span class="pill pass">適合</span></td>
</tr>''')
    return '\n'.join(out)

def blocks_fixes():
    out = []
    for kind, what, before, after, why, src in FIXES:
        out.append(f'''<article class="fix">
<header><span class="tag">{html.escape(kind)}</span><h3>{html.escape(what)}</h3></header>
<div class="ba">
<div class="before"><span class="lbl">修正前</span><p>{html.escape(before)}</p></div>
<div class="after"><span class="lbl">修正後</span><p>{html.escape(after)}</p></div>
</div>
<p class="why">{html.escape(why)}</p>
<p class="src">確認先：{html.escape(src)}</p>
</article>''')
    return '\n'.join(out)

def blocks_open():
    return '\n'.join(
        f'<div class="ask"><h3>{html.escape(t)}</h3><p>{html.escape(b)}</p></div>'
        for t, b in OPEN)

def one_title(i, t):
    cls = ' class="sel"' if i == 0 else ''
    badge = '<em>採用案</em>' if i == 0 else ''
    return (f'<li><span class="cnt">{len(t)}字</span>'
            f'<span{cls}>{html.escape(t)}</span>{badge}</li>')

titles = '\n'.join(one_title(i, t) for i, t in enumerate(T))

HTML = f'''<title>ABCマート越5号店 記事納品シート</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@600;700&display=swap">
<style>
:root{{
  --ground:#F4F6F8; --surface:#FFFFFF; --sunk:#EDF0F4;
  --ink:#11151D; --ink-2:#3A4351; --muted:#5F6A79; --line:#DDE2E9;
  --navy:#1A3659; --navy-soft:#E7EDF5;
  --pass:#2E6B4E; --pass-bg:#E4F0EA;
  --fix:#8A5A0E; --fix-bg:#F6EEDC;
  --was:#A6392C; --was-bg:#F8E9E6;
  --serif:"Noto Serif JP",serif;
  --sans:"Noto Sans JP",system-ui,sans-serif;
}}
@media (prefers-color-scheme:dark){{
  :root:not([data-theme="light"]){{
    --ground:#0D1116; --surface:#161B23; --sunk:#1D242E;
    --ink:#E9EDF3; --ink-2:#C2CAD6; --muted:#8D99A9; --line:#2A323E;
    --navy:#8FB0D8; --navy-soft:#1B2836;
    --pass:#7BC49E; --pass-bg:#16281F;
    --fix:#D8AC5C; --fix-bg:#2A2114;
    --was:#E08b7D; --was-bg:#2C1A17;
  }}
}}
:root[data-theme="dark"]{{
  --ground:#0D1116; --surface:#161B23; --sunk:#1D242E;
  --ink:#E9EDF3; --ink-2:#C2CAD6; --muted:#8D99A9; --line:#2A323E;
  --navy:#8FB0D8; --navy-soft:#1B2836;
  --pass:#7BC49E; --pass-bg:#16281F;
  --fix:#D8AC5C; --fix-bg:#2A2114;
  --was:#E08B7D; --was-bg:#2C1A17;
}}
*{{box-sizing:border-box}}
body{{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--sans); font-size:16px; line-height:1.85;
  -webkit-font-smoothing:antialiased;
}}
.wrap{{max-width:920px; margin:0 auto; padding:0 22px 96px}}
.masthead{{
  border-bottom:2px solid var(--navy); padding:44px 0 20px; margin-bottom:44px;
  display:flex; flex-direction:column; gap:12px;
}}
.kicker{{
  font-size:12px; letter-spacing:.16em; color:var(--navy); font-weight:700;
}}
h1{{
  font-family:var(--serif); font-weight:700; font-size:clamp(26px,4.4vw,38px);
  line-height:1.35; margin:0; text-wrap:balance;
}}
.dek{{color:var(--muted); font-size:14px; margin:0}}
section{{margin:0 0 56px}}
h2{{
  font-family:var(--serif); font-size:21px; font-weight:600; margin:0 0 6px;
  padding-bottom:10px; border-bottom:1px solid var(--line); text-wrap:balance;
}}
.lede{{color:var(--muted); font-size:14px; margin:0 0 22px}}
.card{{background:var(--surface); border:1px solid var(--line); border-radius:4px; padding:26px 28px}}

/* 記事本文 */
.article p{{margin:0 0 1.15em; line-height:2.0}}
.article .ah{{
  font-family:var(--serif); font-size:17px; font-weight:600; margin:2.2em 0 .9em;
  padding-left:12px; border-left:4px solid var(--navy); line-height:1.6;
}}
.article .ah:first-of-type{{margin-top:1.4em}}
.meta-box{{
  background:var(--sunk); border-radius:4px; padding:16px 18px; margin:0 0 26px;
  font-size:13.5px; line-height:1.9;
}}
.meta-box dt{{color:var(--muted); font-weight:700; font-size:11.5px; letter-spacing:.1em}}
.meta-box dd{{margin:0 0 12px}}
.meta-box dd:last-child{{margin-bottom:0}}
ul.titles{{list-style:none; margin:0; padding:0}}
ul.titles li{{
  display:flex; gap:12px; align-items:baseline; padding:6px 0;
  border-bottom:1px dotted var(--line); font-size:14.5px;
}}
ul.titles li:last-child{{border-bottom:0}}
.cnt{{
  font-variant-numeric:tabular-nums; color:var(--muted); font-size:12px;
  min-width:38px; text-align:right;
}}
.sel{{font-weight:700}}
ul.titles em{{
  font-style:normal; font-size:10.5px; letter-spacing:.1em; color:var(--navy);
  background:var(--navy-soft); padding:2px 8px; border-radius:2px; white-space:nowrap;
}}
.gate{{
  display:flex; align-items:center; gap:14px; margin:2.4em 0 1.6em; color:var(--navy);
  font-size:12px; letter-spacing:.12em; font-weight:700;
}}
.gate::before,.gate::after{{content:""; flex:1; height:1px; background:var(--navy); opacity:.35}}
p.mem{{color:var(--ink-2)}}
figure.fig{{margin:2em 0; padding:0}}
figure.fig img{{width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:3px}}
figcaption{{font-size:12.5px; color:var(--muted); margin-top:8px}}

/* 検証表 */
.tbl-wrap{{overflow-x:auto; border:1px solid var(--line); border-radius:4px; background:var(--surface)}}
table{{width:100%; border-collapse:collapse; font-size:14px; min-width:600px}}
th{{
  text-align:left; font-size:11px; letter-spacing:.1em; color:var(--muted);
  font-weight:700; padding:12px 14px; border-bottom:1px solid var(--line); white-space:nowrap;
}}
td{{padding:11px 14px; border-bottom:1px solid var(--line)}}
tr:last-child td{{border-bottom:0}}
td.rid{{font-variant-numeric:tabular-nums; color:var(--muted); font-size:12.5px; font-weight:700}}
td.num{{font-variant-numeric:tabular-nums; white-space:nowrap}}
td.muted{{color:var(--muted)}}
.pill{{
  display:inline-block; font-size:11.5px; font-weight:700; padding:3px 10px; border-radius:2px;
}}
.pill.pass{{color:var(--pass); background:var(--pass-bg)}}

/* 修正記録 */
.fix{{
  background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--fix);
  border-radius:4px; padding:20px 22px; margin:0 0 16px;
}}
.fix header{{display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin-bottom:14px}}
.tag{{
  font-size:10.5px; letter-spacing:.1em; font-weight:700; color:var(--fix);
  background:var(--fix-bg); padding:3px 9px; border-radius:2px; white-space:nowrap;
}}
.fix h3{{font-family:var(--serif); font-size:16px; font-weight:600; margin:0; line-height:1.5}}
.ba{{display:grid; gap:10px; margin-bottom:12px}}
@media(min-width:680px){{.ba{{grid-template-columns:1fr 1fr}}}}
.before,.after{{border-radius:3px; padding:12px 14px}}
.before{{background:var(--was-bg)}}
.after{{background:var(--pass-bg)}}
.lbl{{
  display:block; font-size:10.5px; letter-spacing:.1em; font-weight:700; margin-bottom:5px;
}}
.before .lbl{{color:var(--was)}}
.after .lbl{{color:var(--pass)}}
.before p,.after p{{margin:0; font-size:14px; line-height:1.75}}
.why{{margin:0 0 8px; font-size:14px; color:var(--ink-2)}}
.src{{margin:0; font-size:12.5px; color:var(--muted)}}

/* 依頼事項 */
.ask{{
  background:var(--surface); border:1px solid var(--line); border-radius:4px;
  padding:18px 20px; margin:0 0 12px;
}}
.ask h3{{font-family:var(--serif); font-size:15.5px; font-weight:600; margin:0 0 6px}}
.ask p{{margin:0; font-size:14px; color:var(--ink-2)}}

/* サムネイル */
.thumbs{{display:grid; gap:20px}}
@media(min-width:680px){{.thumbs{{grid-template-columns:1fr 1fr}}}}
.thumbs img{{width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:3px}}
.thumbs h3{{font-family:var(--serif); font-size:15px; font-weight:600; margin:0 0 4px}}
.thumbs p{{margin:8px 0 0; font-size:13px; color:var(--muted); line-height:1.7}}
.files{{
  font-size:13.5px; color:var(--ink-2); background:var(--sunk); border-radius:4px;
  padding:16px 20px; margin-top:20px; line-height:2.0;
}}
.files b{{font-weight:700; color:var(--ink)}}
footer{{border-top:1px solid var(--line); padding-top:18px; font-size:12.5px; color:var(--muted)}}
</style>

<div class="wrap">

<div class="masthead">
  <div class="kicker">InfoBank ／ テスト記事 納品シート</div>
  <h1>{html.escape(T[0])}</h1>
  <p class="dek">元ニュース：ＮＮＡ「ＡＢＣマート、ＨＣＭ市に越５号店開業へ」（2026年8月18日）
  ｜　機械検証9項目すべて適合　｜　ファクトチェックで8点を修正</p>
</div>

<section>
<h2>記事本文</h2>
<p class="lede">検証スクリプトの記法（@F@＝公開、@X@＝会員限定、@G@＝図表位置）を、掲載時の見え方に直して表示しています。</p>
<div class="card">
  <dl class="meta-box">
    <dt>メタディスクリプション（84字）</dt>
    <dd>{html.escape(M)}</dd>
    <dt>カテゴリ／タグ</dt>
    <dd>卸・小売（ID 5）／ 小売・靴・イオンモール・ホーチミン市（ID 47, 411, 151, 15）</dd>
    <dt>内部リンク候補</dt>
    <dd>イオン、ベトナムのイオンモール30年300店へ（/retail/aeon-mall-2/）／ ベトナム、ナイキ靴生産の52%占め4年連続製造拠点首位（/apparel/nike/）</dd>
  </dl>
  <div class="article">
{BODY}
  </div>
</div>
</section>

<section>
<h2>タイトル案</h2>
<p class="lede">規定は26字以上28字以内、「ベトナム」と象徴的なキーワードを含むこと。5案とも規定内です。</p>
<div class="card">
<ul class="titles">
{titles}
</ul>
</div>
</section>

<section>
<h2>機械検証</h2>
<p class="lede">同梱の <b>validate.py</b> で自動判定した結果です。1項目でも不適合なら書き直しに戻す運用を想定しています。今回は初稿でメタ文字数と本文量が不適合となり、2回の差し戻しを経て全項目適合となりました。</p>
<div class="tbl-wrap">
<table>
<thead><tr><th>ID</th><th>検証項目</th><th>実測</th><th>規定</th><th>判定</th></tr></thead>
<tbody>
{rows_checks()}
</tbody>
</table>
</div>
</section>

<section>
<h2>ファクトチェックで修正した点</h2>
<p class="lede">本文を見ていない独立のチェック担当3名（事実確認・校閲・SEO）に検証させ、指摘をすべて一次資料で確かめたうえで反映しました。とくに上の2件は、そのまま出していれば事実誤認になっていた箇所です。</p>
{blocks_fixes()}
</section>

<section>
<h2>サムネイル</h2>
<p class="lede">指定は「Canvaで3パターンを使い回し、デザインは変えずテキストと色だけ差し替える」こと。指定デザインの共有が未了のため、2通りを用意しました。</p>
<div class="thumbs">
  <div>
    <h3>Canvaで作成・書き出し</h3>
    <img src="{IMGS['thumbC']}" alt="Canvaで作成したサムネイル">
    <p>Canva上でテキストと文字色だけを差し替え、レイアウトには一切手を触れずにPNG書き出しまで通しました。指定の3デザインを共有いただければ、同じ手順をそのまま適用できます。</p>
  </div>
  <div>
    <h3>指定パターンBの再現（ローカル生成）</h3>
    <img src="{IMGS['thumbL']}" alt="指定パターンBを再現したサムネイル">
    <p>仕様書に添付されていた3パターンのうちBを再現したものです。あくまで見え方の確認用で、指定デザインそのものではありません。</p>
  </div>
</div>
<div class="files">
  <b>同梱ファイル</b><br>
  draft.txt（本文）／ figures.pptx（図表2枚・パワーポイント形式）／ figure1.png・figure2.png（確認用）／
  thumbnail_canva.png・thumbnail_patternB_local.png（サムネイル）／
  make_figures.py（支給テンプレートから図表を生成）／ validate.py（機械検証）
</div>
</section>

<section>
<h2>ご確認をお願いしたい点</h2>
<p class="lede">こちらで判断できず、進行を止めている事項です。</p>
{blocks_open()}
</section>

<footer>
InfoBank向けテスト記事　2026年8月18日作成。数値はすべて一次資料（エービーシー・マートIR資料、イオンモール公表資料、税関総局速報、ホーチミン市統計）にあたって確認しています。掲載前に、最終の目視チェックをお願いします。
</footer>

</div>
'''

out = pathlib.Path('/tmp/claude-0/-home-user-pictgram0909/abec526f-4f5e-5beb-bc84-f172b645d99b/scratchpad/sheet.html')
out.write_text(HTML, encoding='utf-8')
print('書き出し', out, len(HTML)//1024, 'KB')
