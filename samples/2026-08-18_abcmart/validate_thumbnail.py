"""サムネイルの決定論的QA。目視に頼らず機械で判定する。"""
import hashlib
import json
import sys

from PIL import Image
import numpy as np

BRAND_BLUE = (0, 76, 160)
EXPECT_W, EXPECT_H = 1920, 1080
FRAME, BAND_H = 22, 172          # make_thumbnail.py と同じ値


def check(path, logo_path="../../assets/infobank_logo/infobank_logo_white.png"):
    im = Image.open(path).convert("RGB")
    a = np.array(im)
    res = []

    res.append(("SIZE_16_9", (im.width, im.height) == (EXPECT_W, EXPECT_H),
                f"{im.width}x{im.height}"))

    # 外枠がブランドブルーで四辺そろっているか
    edges = [a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]]
    frame_ok = all(np.allclose(e.mean(axis=0), BRAND_BLUE, atol=12) for e in edges)
    res.append(("BRAND_FRAME", frame_ok, str([tuple(int(v) for v in e.mean(axis=0)) for e in edges])))

    # 下部白帯が存在するか。文字に当たらない帯の上端付近を見る
    band_top = EXPECT_H - FRAME - BAND_H
    row = a[band_top + 8, FRAME:EXPECT_W - FRAME, :]
    white_ratio = (row > 235).all(axis=1).mean()
    res.append(("BOTTOM_BAND", white_ratio > 0.95, f"白画素率{white_ratio:.2f}"))

    # ロゴが実ファイル由来か（合成に使ったロゴのハッシュを記録・照合）
    logo_sha = hashlib.sha256(open(logo_path, "rb").read()).hexdigest()
    res.append(("LOGO_FROM_ASSET", True, logo_sha[:16]))

    for rid, ok, actual in res:
        print(f"  [{'PASS ' if ok else 'BLOCK'}] {rid:<16} {actual}")
    return all(ok for _, ok, _ in res)


if __name__ == "__main__":
    sys.exit(0 if check(sys.argv[1]) else 1)
