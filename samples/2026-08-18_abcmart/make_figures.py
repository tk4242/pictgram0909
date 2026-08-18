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
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

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
                "出所：エービーシー・マート「2027年2月期第1四半期決算」よりInfoBankが作成",
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
                "出所：各社公表資料よりInfoBankが作成。ユニクロは2026年7月時点、ABCマートは新店を含む",
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


def force_data_labels(chart):
    """系列ごとに c:dLbls を差し込み、値ラベルを必ず表示させる。

    python-pptx の data_labels API はテンプレート側の設定に負けることがあるため、
    XML を直接組み立てる。c:dLbls は c:cat より前に置く必要がある（スキーマ順序）。
    """
    plot_area = chart._chartSpace.find(f".//{{{C}}}plotArea")
    for ser in plot_area.iter(f"{{{C}}}ser"):
        for old in ser.findall(f"{{{C}}}dLbls"):
            ser.remove(old)
        dlbls = etree.SubElement(ser, f"{{{C}}}dLbls")
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
