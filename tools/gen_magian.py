import json, re, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'tools' / 'data' / 'magian'
from collections import defaultdict

CACHE.mkdir(parents=True, exist_ok=True)
LSB_DATA = CACHE / 'magian_data.lua'
LSB_ENUM = CACHE / 'item.lua'

db=sqlite3.connect(ROOT / 'data' / 'fanxi.db'); db.row_factory=sqlite3.Row
items={r['item_id']:dict(r) for r in db.execute("SELECT item_id,name,equip_slot,level,rare,ex FROM items")}

# --- LSB trial data (cached) ---
if not LSB_DATA.exists():
    subprocess.run(['curl','-sSL','--max-time','60','-o',str(LSB_DATA),
        'https://raw.githubusercontent.com/LandSandBoat/server/base/scripts/globals/magian_data.lua'], check=True)
if not LSB_ENUM.exists():
    subprocess.run(['curl','-sSL','--max-time','60','-o',str(LSB_ENUM),
        'https://raw.githubusercontent.com/LandSandBoat/server/base/scripts/enum/item.lua'], check=True)
src=LSB_DATA.read_text()
body=src.split('xi.magian.trials =',1)[1]
blocks=re.split(r'\n    \[(\d+)\] =', body)[1:]
trials={}
for i in range(0,len(blocks),2):
    tid=int(blocks[i]); block=blocks[i+1]
    def item(which):
        m=re.search(which+r'\s*=\s*\n?\s*\{[^}]*?itemId\s*=\s*xi\.item\.([A-Z0-9_]+)',block,re.S)
        if not m: return None
        em=re.search(r'^\s+'+m.group(1)+r'\s*=\s*(\d+),', LSB_ENUM.read_text(), re.M)
        return int(em.group(1)) if em else None
    def augs(which):
        start=block.find(which)
        if start<0: return []
        seg=block[start:start+800]
        return [[int(a),int(b)] for a,b in re.findall(r'\{\s*(\d+)\s*,\s*(-?\d+)\s*\}',seg)]
    prev=re.search(r'previousTrial\s*=\s*(\d+)',block)
    num=re.search(r'numRequired\s*=\s*(\d+)',block)
    off=re.search(r'textOffset\s*=\s*(\d+)',block)
    trials[tid]={'id':tid,'prev':int(prev.group(1)) if prev else 0,
                 'req':item('requiredItem'),'reward':item('rewardItem'),
                 'augments':augs('rewardItem'),
                 'num':int(num.group(1)) if num else 0,
                 'offset':int(off.group(1)) if off else 0}

# --- wiki i119 augment trials (the pages that use the augment template) ---
PAGES=['Dagger_Trials','Sword_Trials','Katana_Trials','Archery_Trials','Marksmanship_Trials']
def fetch_title(urlname):
    html=subprocess.run(['curl','-sS','--max-time','30','https://www.bg-wiki.com/ffxi/'+urlname],capture_output=True,text=True).stdout
    m=re.search(r'<title>(.*?) - FFXI Wiki</title>',html,re.S)
    return m.group(1).strip() if m else None
def wikitext(title):
    out=subprocess.run(['curl','-sS','--max-time','40','-G','https://www.bg-wiki.com/api.php',
        '--data-urlencode','action=parse','--data-urlencode','page='+title,
        '--data-urlencode','prop=wikitext','--data-urlencode','format=json'],capture_output=True,text=True).stdout
    try: return json.loads(out)['parse']['wikitext']['*']
    except Exception: return ''
def clean(t):
    t=re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]',r'\1',t)
    t=t.replace('{{augment}}','')
    t=re.sub(r'\{\{[^}]*\}\}','',t)
    t=re.sub(r'<[^>]+>',' ',t)
    t=re.sub(r"'''|\"",'',t)
    return re.sub(r'\s+',' ',t).strip(' ,')
def rows_for(page):
    title=fetch_title(page)
    if not title: return []
    wt=wikitext(title)
    out=[]
    for tbl in re.findall(r'\{\| class="magiantrials".*?\n\|\}',wt,re.S):
        if '{{augment}}' not in tbl: continue
        rows=[r for r in re.split(r'\n\|-',tbl)][1:]
        parsed=[]
        for r in rows:
            cs=[]
            for c in re.split(r'\n\|(?!\|)','\n'+r):
                c=c.strip()
                if not c: continue
                m=re.match(r'^(?:colspan="?\d+"?|rowspan="?\d+"?|align="?[a-z]+"?|style="[^"]*"|\s)*\|(.*)$',c,re.S)
                cs.append(m.group(1) if m else c)
            ts=[int(x) for c in cs for x in re.findall(r'\[\[Trial (\d+)\]\]',c)]
            rs=[]
            for c in cs:
                lm=re.search(r'link=([^|\]\n]+)',c)
                am=re.search(r'\{\{augment\}\}(.*)',c,re.S)
                if lm and am: rs.append((lm.group(1).strip().lstrip(':'),clean(am.group(1).split('\n')[0])))
            parsed.append((ts,rs))
        for i in range(len(parsed)-1):
            ts=parsed[i][0]; rs=parsed[i+1][1]
            if ts and rs and len(ts)==len(rs) and len(rs)>1:
                for tid,(name,text) in zip(ts,rs):
                    if text and name in {v['name'] for v in items.values()}:
                        out.append((name,tid,text))
    return out

# map augment text to (id,value) pairs for the wiki i119 rows
def picks(text):
    t=text.replace(' ','')
    rows=[]
    dm=re.search(r'DMG\+(\d+)',t)
    if dm: rows.append([0x2E4,int(dm.group(1))-1])
    st=re.search(r'StoreTP\+(\d+)',t)
    if st: rows.append([0x08E,int(st.group(1))-1])
    tp=re.search(r'TPBonus\+(\d+)',t)
    if tp: rows.append([0x161,int(tp.group(1))//50-1])
    wsd=re.search(r'WeaponSkillDamage\+(\d+)%',t)
    if wsd: rows.append([0x147,int(wsd.group(1))-1])
    dl=re.search(r'Delay\+(\d+)',t)
    if dl: rows.append([0x2F9,int(dl.group(1))-33])
    return rows

wiki_rows=[]
for p in PAGES:
    try:
        got=rows_for(p)
    except Exception as e:
        print('wiki',p,'ERR',e); got=[]
    print('wiki',p,len(got))
    wiki_rows+=got
    time.sleep(0.5)

by_name={v['name']:k for k,v in items.items()}
item_trials=defaultdict(list)
for t in trials.values():
    if t['req'] is None: continue
    item_trials[t['req']].append({'id':t['id'],'reward':t['reward'],'augments':t['augments'],
                                 'num':t['num'],'offset':t['offset']})
for name,tid,text in wiki_rows:
    iid=by_name.get(name)
    if not iid: continue
    item_trials[iid].append({'id':tid,'reward':iid,'augments':picks(text),'text':[text],'wiki':True})

# items with at least one trial, plus every reward item (so their names resolve)
keep=set(item_trials)
for t in trials.values():
    if t['reward']: keep.add(t['reward'])
out_items={}
for iid in sorted(keep):
    it=items.get(iid)
    if not it: continue
    trials_for=sorted(item_trials.get(iid,[]), key=lambda x:x['id'])
    out_items[str(iid)]={'name':it['name'],'slot':it['equip_slot'] or '','level':it['level'],
                         'rare':it['rare'],'ex':it['ex'],'trials':trials_for}
data={'note':'Trial of the Magians. The classic trials and the Empyrean/Relic armour come from LandSandBoat\'s magian_data.lua (item ids, reward augments and trial ids); the i119 augment paths (Centovente and the Empyrean Weapon Skill finals) were read from the BG Wiki trial pages. Applying a trial hands you its reward item and writes the Magian block (4 augment slots plus the trial id).',
      'sources':['https://www.bg-wiki.com/ffxi/Category:Trial_of_the_Magians','https://github.com/LandSandBoat/server/blob/base/scripts/globals/magian_data.lua'],
      'catalog_size':len(out_items),
      'items':out_items}
open(ROOT / 'data' / 'magian.json','w').write(json.dumps(data,indent=0,separators=(',',':')))
print('items',len(out_items),'trials',sum(len(v['trials']) for v in out_items.values()),'bytes',len((ROOT / 'data' / 'magian.json').read_bytes()))
