"""claims.json が draft.txt の現在の本文と乖離していないか検査する。

記事を直したのに claim を直し忘れると、ファクトチェック表が古い文を検証したことになる。
実際にその取りこぼしが起きたため、機械で検出できるようにした。
""",

import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
body = unicodedata.normalize("NFC", (HERE / "draft.txt").read_text(encoding="utf-8"))
claims = json.loads((HERE / "claims.json").read_text(encoding="utf-8"))

# claim文に含まれる特徴的な数値・固有名詞が本文に存在するかを見る
def tokens(text):
    import re
    return [t for t in re.findall(r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?|[一-龥ァ-ヶ]{3,}", text)]

stale = []
for c in claims:
    toks = tokens(unicodedata.normalize("NFC", c["claim"]))
    missing = [t for t in toks if t not in body]
    # 全トークンが本文にあることまでは求めない（claimは要約なので）。
    # 半分以上が本文に無いものは、記事修正の反映漏れとみなす。
    if toks and len(missing) > len(toks) * 0.5:
        stale.append((c["claim_id"], missing[:5]))

for cid, miss in stale:
    print(f"  [WARN] {cid}: 本文に見当たらない語 {miss}")
print(f"claim同期チェック: {len(claims)}件中 要確認 {len(stale)}件")
sys.exit(1 if stale else 0)
