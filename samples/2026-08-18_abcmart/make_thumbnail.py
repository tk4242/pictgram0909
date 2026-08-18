"""InfoBank記事サムネイルを参考資料の型どおりに合成する。

参考画像3点から抽出した3つの型のうち TYPE C（解説型）を実装する。
    ブランドブルーの外枠 / 左上のカテゴリラベル / 白抜き大見出し
    / 写真 / 右下のInfoBankロゴ枠 / 下部の白帯サブタイトル

設計上の要点:
  - ロゴは描かない。テンプレートpptxから取り出した実ロゴ画像を貼る（設計書§18 偽ロゴ禁止）。
  - 文字は生成AIに描かせない。ここで決定論的に描画する。
  - 文字サイズは枠幅に収まるまで自動で縮める（切れ・はみ出しを構造的に防ぐ）。

使い方: python3 make_thumbnail.py <背景写真> <出力先.png>
"""
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BRAND_BLUE = (0, 76, 160)          # 実ロゴから採取。図表タイトル色 004CA0 と一致
DARK = (10, 21, 36)
WHITE = (255, 255, 255)
INK = (21, 21, 21)

FRAME = 22                          # 外枠の太さ
LABEL_H = 116                       # カテゴリラベルの高さ
BAND_H = 172                        # 下部白帯の高さ
FONT_BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_JP_INDEX = 0                   # ttc内の Noto Sans CJK JP

LOGO = "assets/infobank_logo/infobank_logo_white.png"

CONTENT = {
    "category": "企業",
    "title": "ABCマート ベトナム5号店",
    "subtitle": "イオンモールに29日開業、店舗網は5店へ",
}


def font(px):
    return ImageFont.truetype(FONT_BLACK, px, index=FONT_JP_INDEX)


def fit(draw, text, max_w, start_px, min_px=28, stroke=0):
    """max_w に収まる最大のフォントを返す。切れ・はみ出しを構造的に排除する。"""
    for px in range(start_px, min_px - 1, -2):
        f = font(px)
        if draw.textlength(text, font=f, ) + stroke * 2 <= max_w:
            return f
    return font(min_px)


def cover(img, box_w, box_h):
    """アスペクト比を保ったまま box を埋める（中央基準トリミング）。"""
    scale = max(box_w / img.width, box_h / img.height)
    im = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (im.width - box_w) // 2
    top = (im.height - box_h) // 2
    return im.crop((left, top, left + box_w, top + box_h))


def build(bg_path, out_path, content=CONTENT):
    canvas = Image.new("RGB", (W, H), BRAND_BLUE)

    # ── 写真（外枠の内側を埋める） ──
    inner = (FRAME, FRAME, W - FRAME, H - FRAME)
    canvas.paste(cover(Image.open(bg_path).convert("RGB"),
                       inner[2] - inner[0], inner[3] - inner[1]), (inner[0], inner[1]))

    d = ImageDraw.Draw(canvas)

    # ── 左上：カテゴリラベル（ブランドブルーの塗り＋白文字） ──
    lab_f = font(64)
    lab_w = round(d.textlength(content["category"], font=lab_f)) + 96
    d.rectangle([FRAME, FRAME, FRAME + lab_w, FRAME + LABEL_H], fill=BRAND_BLUE)
    _, top_off, _, bot_off = d.textbbox((0, 0), content["category"], font=lab_f)
    d.text((FRAME + lab_w / 2, FRAME + LABEL_H / 2 - (top_off + bot_off) / 2),
           content["category"], font=lab_f, fill=WHITE, anchor="mm")

    # ── 上部：白抜き大見出し（縁取りで写真の上でも読める） ──
    title_x = FRAME + lab_w + 40
    stroke = 9
    t_f = fit(d, content["title"], W - title_x - FRAME - 40, 118, stroke=stroke)
    d.text((title_x, FRAME + LABEL_H / 2), content["title"], font=t_f,
           fill=WHITE, anchor="lm", stroke_width=stroke, stroke_fill=DARK)

    # ── 下部：白帯＋サブタイトル ──
    band_top = H - FRAME - BAND_H
    d.rectangle([FRAME, band_top, W - FRAME, H - FRAME], fill=WHITE)
    s_f = fit(d, content["subtitle"], W - 2 * FRAME - 120, 88)
    d.text((W / 2, band_top + BAND_H / 2), content["subtitle"], font=s_f,
           fill=INK, anchor="mm")

    # ── 右下：InfoBankロゴ（実ロゴを濃紺の枠に置く。描き起こさない） ──
    logo = Image.open(LOGO).convert("RGBA")
    box_h, pad = 118, 34
    lw = round(logo.width * (box_h - pad) / logo.height)
    logo = logo.resize((lw, box_h - pad), Image.LANCZOS)
    box_w = lw + pad * 2
    bx, by = W - FRAME - box_w, band_top - box_h
    d.rectangle([bx, by, bx + box_w, by + box_h], fill=DARK)
    canvas.paste(logo, (bx + pad, by + pad // 2), logo)

    canvas.save(out_path)
    print(f"生成: {out_path}  {W}x{H}  見出し{t_f.size}px / サブ{s_f.size}px")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
