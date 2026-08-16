import re, unicodedata, sys, json

src = open('article.md', encoding='utf-8').read()
fm, body = src.split('---', 2)[1], src.split('---', 2)[2]

titles = re.findall(r'^  - (.+)$', fm, re.M)
meta   = re.search(r'^meta_description: (.+)$', fm, re.M).group(1).strip()
gate   = re.search(r'^gate_after: (\w+)$', fm, re.M).group(1)

def n(s): return len(unicodedata.normalize('NFC', s.strip()))

paras = re.findall(r'^p(\d+): (.+)$', body, re.M)
lead  = re.search(r'## LEAD\n\n(.+)', body).group(1)
h2s   = re.findall(r'^## H2-\d+ (.+)$', body, re.M)

body_chars = n(lead) + sum(n(t) for _, t in paras)
results = []
def check(rid, sev, ok, field, actual, expected, msg=''):
    results.append(dict(rule=rid, sev=sev, ok=bool(ok), field=field,
                        actual=str(actual), expected=expected, msg=msg))

print('=' * 78)
print('  タイトル案の文字数')
print('=' * 78)
valid_titles = []
for i, t in enumerate(titles):
    c, has_vn = n(t), 'ベトナム' in t
    ok = 26 <= c <= 28 and has_vn
    if ok: valid_titles.append(t)
    print(f'  {"OK " if ok else "NG "} {c:>2}字  {"ベトナム有" if has_vn else "ベトナム無"}  {t}')

check('T01', 'blocker', all(26 <= n(t) <= 28 for t in titles), 'titles',
      [n(t) for t in titles], '26-28')
check('T02', 'blocker', all('ベトナム' in t for t in titles), 'titles',
      f'{sum("ベトナム" in t for t in titles)}/{len(titles)}件', '全件に含む')
check('T03', 'blocker', len(valid_titles) >= 1 and len(titles) >= 3, 'titles',
      f'案{len(titles)}件・合格{len(valid_titles)}件', '案3件以上・合格1件以上')
check('M01', 'blocker', 80 <= n(meta) <= 90, 'meta_description', n(meta), '80-90')
check('B01', 'blocker', 1275 <= body_chars <= 1725, 'body', body_chars, '1275-1725')
check('B02', 'blocker', len(h2s) >= 2, 'sections', f'{len(h2s)}本', '2本以上')

kw = ['ベトナム', '貿易', '輸入', '輸出', '対米', '対中', '電子部品', '赤字', '黒字']
h2_ng = [h for h in h2s if not any(k in h for k in kw)]
check('B03', 'warn', not h2_ng, 'sections', f'キーワード無し{len(h2_ng)}本', '全H2に1語以上')

num_re = re.compile(r'[0-9０-９]')
gate_i = int(gate[1:])
pos = 0; total = body_chars; acc = n(lead)
for pid, t in paras:
    if int(pid) <= gate_i: acc_gate = acc + 0
    acc += n(t)
acc = n(lead); public = acc
for pid, t in paras:
    acc += n(t)
    if int(pid) == gate_i: public = acc
ratio = public / body_chars
check('G01', 'blocker', 0.60 <= ratio <= 0.70, 'gate_after',
      f'{ratio*100:.1f}%（{public}/{body_chars}字）', '60-70%')
check('F01', 'blocker', body.count('[FIGURE') == 2, 'figures', body.count('[FIGURE'), '2件')

print()
print('=' * 78)
print('  機械検証（validators/）')
print('=' * 78)
ng = 0
for r in results:
    mark = 'PASS' if r['ok'] else ('BLOCK' if r['sev'] == 'blocker' else 'WARN ')
    if not r['ok'] and r['sev'] == 'blocker': ng += 1
    print(f"  [{mark:5}] {r['rule']}  {r['field']:<18} 実測={r['actual']:<24} 期待={r['expected']}")

print()
print(f'  リード文        : {n(lead)}字')
print(f'  本文合計        : {body_chars}字（リード＋本文16段落）')
print(f'  H2見出し        : {len(h2s)}本')
print(f'  公開部分        : {public}字 / 全体{body_chars}字 = {ratio*100:.1f}%')
print(f'  メタディスク    : {n(meta)}字')
print()
print(f'  >>> blocker違反 {ng}件')
