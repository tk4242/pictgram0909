"""ABCマート越5号店の記事用に、支給テンプレートから図表2枚のpptxを生成する。

テンプレートのネイティブ図形（chart オブジェクト）をそのまま流用し、
データだけを replace_data で差し替えることで書式・配色・フォントを完全に保持する。
図形は index ではなく shape.name で参照する（テンプレート改訂に強くするため）。

使い方: python3 make_figures.py <chart_template.pptx> <出力先.pptx>
"""
import sys
from copy import deepcopy

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData

C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

# テンプレートのHard Rule（原本 slide31「基本的な図表の構成」に明記）
#   フォント：Meiryo UI ／ 文字サイズ（タイトル以外）：14pt
FONT = "Meiryo UI"
AXIS_PT = 14

# 流用するテンプレートのスライド（0始まり）
SRC_BAR = 120     # 横棒グラフ（BAR_CLUSTERED）
SRC_COLUMN = 114  # 縦棒グラフ（COLUMN_CLUSTERED）

FIGURES = [
    {
        "slide": SRC_BAR,
        "chart": "グラフ 10",
        "categories": ["フィリピン", "米国", "ベトナム", "台湾", "韓国"],
        "series": ("店舗数", [2, 7, 4, 63, 317]),
        "number_format": '0',
        "text": {
            # 文字数は枠幅に収まる範囲に抑える（テキスト ボックス 4 は約15cm＝全角24字が上限）
            "テキスト プレースホルダー 1": "韓国317店に対しベトナムは4店、今回の開業で5店に",
            "テキスト ボックス 4": "ABCマートの海外店舗数（2026年3月末時点）",
            "テキスト ボックス 11": "単位：店",
            "テキスト プレースホルダー 3":
                "出所：エービーシー・マート「2027年2月期第1四半期決算」をもとにInfoBank作成",
        },
        # 旧データ用に手打ちされた数値ラベル・装飾を除去する
        "drop": ["テキスト ボックス 17", "テキスト ボックス 18", "テキスト ボックス 19",
                 "テキスト ボックス 20", "テキスト ボックス 21", "テキスト ボックス 22",
                 "図 12", "図 13", "図 14", "図 15", "図 16"],
    },
    {
        "slide": SRC_COLUMN,
        "chart": "グラフ 9",
        "categories": ["ユニクロ", "無印良品", "ABCマート"],
        "series": ("店舗数", [32, 17, 5]),
        "number_format": '0',
        "text": {
            "テキスト プレースホルダー 1": "ユニクロ32店・無印良品17店に対し、ABCマートは5店",
            "テキスト ボックス 5": "日系専門店チェーンのベトナム店舗数（単位：店）",
            # 単位はタイトルに含めた。この枠は棒に重なる位置にあるため空にする
            "テキスト ボックス 8": "",
            "テキスト ボックス 10": "※無印良品は2025年11月時点",
            "テキスト プレースホルダー 3":
                "出所：各社公表資料をもとにInfoBank作成。ユニクロは2026年7月時点、ABCマートは新店を含む",
        },
        "drop": [],
    },
]


def set_text(shape, value):
    """段落・ラン単位の書式を保ったまま本文だけ差し替える。"""
    tf = shape.text_frame
    para = tf.paragraphs[0]
    if para.runs:
        para.runs[0].text = value
        for extra in para.runs[1:]:
            extra._r.getparent().remove(extra._r)
    else:
        para.add_run().text = value
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)


def force_all_category_labels(chart):
    """項目軸のラベルを間引かせない（c:tickLblSkip = 1）。

    既定の auto では、フォント幅が変わった際にレンダラーがラベルを1つおきに
    落とすことがある（実際に「米国」「台湾」が消える事故が起きた）。
    スキーマ上 c:tickLblSkip は c:lblOffset の後、c:noMultiLvlLbl の前に置く。
    """
    for cat_ax in chart._chartSpace.iter(f"{{{C}}}catAx"):
        for old in cat_ax.findall(f"{{{C}}}tickLblSkip"):
            cat_ax.remove(old)
        skip = etree.Element(f"{{{C}}}tickLblSkip")
        skip.set("val", "1")
        anchor = cat_ax.find(f"{{{C}}}noMultiLvlLbl")
        if anchor is None:
            anchor = cat_ax.find(f"{{{C}}}tickMarkSkip")
        if anchor is None:
            cat_ax.append(skip)
        else:
            anchor.addprevious(skip)


def enforce_font(root, font=FONT):
    """スライド／グラフ内の全テキストへ Meiryo UI を明示指定する。

    流用元にした過去事例スライドは typeface を持たずテーマ（Calibri/游ゴシック）へ
    フォールバックする作りのため、そのままではテンプレートのHard Ruleを満たさない。
    latin / ea / cs の3系統すべてを指定しないと、和文だけ別フォントに落ちる。
    """
    count = 0
    for rpr in root.iter():
        # a:rPr / a:defRPr / a:endParaRPr すべてが typeface の親になり得る
        if etree.QName(rpr).localname not in ("rPr", "defRPr", "endParaRPr"):
            continue
        for kind in ("latin", "ea", "cs"):
            tag = f"{{{A}}}{kind}"
            el = rpr.find(tag)
            if el is None:
                el = etree.SubElement(rpr, tag)
                # a:latin/ea/cs は fill 系の後ろに来る必要があるため末尾追加で問題ない
            el.set("typeface", font)
        count += 1
    return count


def _txpr(size_pt):
    """c:txPr（a:bodyPr / a:lstStyle / a:p>a:pPr>a:defRPr）を組み立てて返す。"""
    txpr = etree.Element(f"{{{C}}}txPr")
    etree.SubElement(txpr, f"{{{A}}}bodyPr")
    etree.SubElement(txpr, f"{{{A}}}lstStyle")
    p = etree.SubElement(txpr, f"{{{A}}}p")
    ppr = etree.SubElement(p, f"{{{A}}}pPr")
    defrpr = etree.SubElement(ppr, f"{{{A}}}defRPr")
    defrpr.set("sz", str(int(size_pt * 100)))
    for kind in ("latin", "ea", "cs"):
        etree.SubElement(defrpr, f"{{{A}}}{kind}").set("typeface", FONT)
    etree.SubElement(p, f"{{{A}}}endParaRPr").set("lang", "ja-JP")
    return txpr


def set_axis_text_size(chart, size_pt=AXIS_PT):
    """軸ラベルを規定サイズへ揃える。

    テンプレートのHard Ruleは「文字サイズ（タイトル以外）：14pt」。
    流用元は24ptで、ルール違反な上に幅が広くレンダラーが項目ラベルを間引く
    （「米国」「台湾」が消える事故が実際に起きた）。
    c:txPr は c:crossAx より前に置く必要がある（スキーマ順序）。
    """
    for ax_name in ("catAx", "valAx"):
        for ax in chart._chartSpace.iter(f"{{{C}}}{ax_name}"):
            for old in ax.findall(f"{{{C}}}txPr"):
                ax.remove(old)
            cross_ax = ax.find(f"{{{C}}}crossAx")
            txpr = _txpr(size_pt)
            if cross_ax is None:
                ax.append(txpr)
            else:
                cross_ax.addprevious(txpr)


def force_data_labels(chart, size_pt=AXIS_PT):
    """系列ごとに c:dLbls を差し込み、値ラベルを必ず表示させる。

    python-pptx の data_labels API はテンプレート側の設定に負けることがあるため、
    XML を直接組み立てる。c:dLbls は c:cat より前に置く必要がある（スキーマ順序）。
    c:dLbls の中では c:txPr が show* 系より前。
    """
    plot_area = chart._chartSpace.find(f".//{{{C}}}plotArea")
    for ser in plot_area.iter(f"{{{C}}}ser"):
        for old in ser.findall(f"{{{C}}}dLbls"):
            ser.remove(old)
        dlbls = etree.SubElement(ser, f"{{{C}}}dLbls")
        dlbls.append(_txpr(size_pt))
        for tag, val in [("showLegendKey", "0"), ("showVal", "1"), ("showCatName", "0"),
                         ("showSerName", "0"), ("showPercent", "0"), ("showBubbleSize", "0")]:
            etree.SubElement(dlbls, f"{{{C}}}{tag}").set("val", val)
        cat = ser.find(f"{{{C}}}cat")
        if cat is not None:
            ser.remove(dlbls)
            cat.addprevious(dlbls)


def build(template_path, out_path):
    prs = Presentation(template_path)
    keep = [f["slide"] for f in FIGURES]

    for spec in FIGURES:
        slide = prs.slides[spec["slide"]]
        by_name = {sh.name: sh for sh in slide.shapes}

        for name in spec["drop"]:
            shape = by_name.get(name)
            if shape is not None:
                shape._element.getparent().remove(shape._element)

        for name, value in spec["text"].items():
            shape = by_name.get(name)
            if shape is None:
                raise KeyError(f"slide {spec['slide']}: 図形 {name!r} が見つかりません")
            set_text(shape, value)

        chart_shape = by_name.get(spec["chart"])
        if chart_shape is None or not chart_shape.has_chart:
            raise KeyError(f"slide {spec['slide']}: グラフ {spec['chart']!r} が見つかりません")
        data = CategoryChartData()
        data.categories = spec["categories"]
        label, values = spec["series"]
        data.add_series(label, values, spec["number_format"])
        chart_shape.chart.replace_data(data)
        force_data_labels(chart_shape.chart)
        force_all_category_labels(chart_shape.chart)
        set_axis_text_size(chart_shape.chart)

        # 文字を差し替えた後にフォントを固定する（順序が逆だと新しいランが素通りする）
        n = enforce_font(slide.shapes._spTree)
        n += enforce_font(chart_shape.chart._chartSpace)
        print(f"  slide {spec['slide']}: {FONT} を {n} 箇所へ適用")

    # 使わないスライドを削除し、参照が切れたメディアも一緒に落とす（ファイルサイズ対策）。
    # drop_rel を伴わない削除だと画像が残り、ファイルが十数MBに膨らむ。
    sld_id_lst = prs.slides._sldIdLst
    kept = {}
    for i, sld_id in enumerate(list(sld_id_lst)):
        if i in keep:
            kept[i] = sld_id
            continue
        sld_id_lst.remove(sld_id)
        prs.part.drop_rel(sld_id.get(R))

    # 残したスライドを FIGURES の並び順（図表1→図表2）に組み替える
    for i in keep:
        sld_id_lst.append(kept[i])

    prs.save(out_path)
    print(f"生成: {out_path}（{len(keep)}枚）")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
