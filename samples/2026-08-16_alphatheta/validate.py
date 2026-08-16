import unicodedata,sys
L=[l for l in open(sys.argv[1],encoding='utf-8').read().splitlines() if l.strip()]
n=lambda s: len(unicodedata.normalize('NFC',s.strip()))
g=lambda p:[l[len(p):] for l in L if l.startswith(p)]
T,M,H,F,X,G = g('@T@'),g('@M@')[0],g('@H@'),g('@F@'),g('@X@'),g('@G@')
pub,mem = sum(map(n,F)), sum(map(n,X)); tot=pub+mem
kw=['ベトナム','DJ','ファブレス','生産','工場','電子','日系']
h2ng=[h for h in H if not any(k in h for k in kw)]
def r(rid,lab,act,exp,ok):
    print(f"  [{'PASS ' if ok else 'BLOCK'}] {rid}  {lab:<20} 実測={act:<26} 期待={exp}")
print('='*74)
for t in T: print(f"  {'OK ' if 26<=n(t)<=28 and 'ベトナム' in t else 'NG '} {n(t):>2}字  {t}")
print('='*74)
r('T01','タイトル文字数',str([n(t) for t in T]),'26-28',all(26<=n(t)<=28 for t in T))
r('T02','「ベトナム」含有',f'{sum("ベトナム" in t for t in T)}/{len(T)}件','全件',all('ベトナム' in t for t in T))
r('T03','タイトル案の数',f'{len(T)}案','3案以上',len(T)>=3)
r('M01','メタディスクリプション',f'{n(M)}字','80-90',80<=n(M)<=90)
r('B01','本文文字数',f'{tot}字','1275-1725',1275<=tot<=1725)
r('B02','H2見出し',f'{len(H)}本','2本以上',len(H)>=2)
r('B03','H2のキーワード',f'未充足{len(h2ng)}本','全H2',not h2ng)
r('F01','図表',f'{len(G)}枚','2枚',len(G)==2)
r('G01','公開比率',f'{pub/tot*100:.1f}%（{pub}/{tot}字）','60-70%',0.60<=pub/tot<=0.70)
print(f"\n  公開 {pub}字 / 会員限定 {mem}字 / 合計 {tot}字（目安1,500字 {tot-1500:+d}字）")
