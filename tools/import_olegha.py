"""Import a dated, immutable Kutuzovsky snapshot; never modify the application."""
import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--date', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
source = Path(a.source)
assert source.name == 'server_103_Kutuzovskiy'
snap = root / 'sources' / 'olegha' / a.date
out = root / 'docs' / 'current'
assert not snap.exists(), 'Snapshot already exists; use a new date, do not overwrite evidence'
out.mkdir(parents=True, exist_ok=True)
snap.mkdir(parents=True)
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
write = lambda path, text: path.write_text(text, encoding='utf-8')
files = []
for path in sorted(source.rglob('*')):
    if not path.is_file():
        continue
    rel = path.relative_to(source)
    raw = path.read_bytes()
    dest = snap / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    files.append({'path': rel.as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

# Explicit mapping to the previously selected working editions, not fuzzy titles.
old = {'ВС':'laws/0249d290','Выборы':'laws/7f3c8402','ГИБДД':'laws/a8bebbda','Госслуж.':'laws/abd5afc7','Гостайна':'laws/4aa7aa8a','Здрав.':'laws/21652f3b','КоАП':'codes/c6c2de07','Конст.':'codes/a4c85ebb','Минист.':'laws/a3938895','НЕПР':'laws/5df3eab4','Оруж.':'laws/237a37a1','Парт.':'laws/9bf15c2f','ПДД':'codes/6b70bcac','ПК':'codes/557b2009','Полиц.':'laws/d5436eb5','Прав.':'laws/a772e056','Предпр.':'laws/b0fda591','Прок.':'laws/f7709d65','Режим.':'laws/17351cb8','СК':'laws/b26baee5','Суд.':'laws/cd05d5d8','Терр.':'laws/d7b145dd','ТК':'codes/d0b96404','УК':'codes/6c67fbe0','ФСБ':'laws/a39fc8f1','ФСО':'laws/a62a928d','Этика':'codes/a5678cae'}
old_rules = {'1':'docs/site/site-10.md','11':'sources/snapshot/state-rules-current.txt','12':'docs/rules/ee0cd4f3.md','3':'docs/rules/8d84dd4c.md','5':'docs/rules/2d207ca8.md','14':'docs/rules/martial-law-rules.md','15':'docs/rules/ed1663b7.md'}
# Locate legacy rules by their manifest titles where filenames differ.
manifest = read(root / 'manifest.json')
for rid, titlepart in [('14','военного положения')]:
    candidates = [x['document'] for x in manifest if titlepart in x['title'].lower()]
    if candidates:
        old_rules[rid] = candidates[0]
if not (root / old_rules['11']).exists():
    old_rules['11'] = 'docs/site/site-09.md'

docs, search, comparisons, mappings = [], [], [], {}
diffdir = root / 'changes' / ('olegha-' + a.date)
diffdir.mkdir(parents=True, exist_ok=True)
def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[#*\u200b]', '', s)).strip().casefold()
def register(slug, title, chunks, rawpath, legacy, kind):
    name = slug + '.md'
    header = f'# {title}\n\nРабочий источник по указанию пользователя: снимок Olegha77 AI от {a.date}. Дата импорта не доказывает дату вступления норм в силу.\n\n[Исходные данные](../../{rawpath}) · [Поправки и ограничения](../../AMENDMENTS.md) · [Каталог](README.md)\n\n'
    if slug == 'rules-11':
        header += '**ПГО 9.9: применять 48 часов по явной поправке пользователя. В сыром источнике 24 часа — сохранённое расхождение, не отмена поправки.**\n\n'
    body = '\n\n'.join(chunks)
    write(out / name, header + body + '\n')
    docs.append({'title':title,'path':'docs/current/'+name,'source':rawpath,'kind':kind})
    if legacy and (root / legacy).exists():
        previous = (root / legacy).read_text(encoding='utf-8-sig')
        delta = list(difflib.unified_diff(previous.splitlines(), body.splitlines(), fromfile=legacy, tofile='docs/current/'+name, lineterm=''))
        write(diffdir / (slug+'.diff'), '\n'.join(delta)+'\n')
        # Text containment comparison: differences include formatting/extraction, not certified amendments.
        oldnorm = norm(previous)
        entries = [x for x in search if x['document']=='docs/current/'+name]
        contained = sum(norm(x['text']) in oldnorm for x in entries)
        comparisons.append({'title':title,'old':legacy,'new':'docs/current/'+name,'entries':len(entries),'exact_normalized_containment':contained,'diff':str((diffdir/(slug+'.diff')).relative_to(root)).replace('\\','/')})
        mappings[legacy]='docs/current/'+name
    else:
        comparisons.append({'title':title,'old':None,'new':'docs/current/'+name,'note':'Нет сопоставленного прежнего рабочего документа; материал добавлен, это не утверждение о новизне закона.'})

for path in sorted((snap/'toc').glob('*.json')):
    d=read(path); chunks=[]
    slug='law-'+path.stem.rstrip('.')
    for ch in d['chapters']:
        chunks.append('## '+ch['name'])
        for i,it in enumerate(ch['items']):
            chunks.append(f"### Статья {it['article']}. {it.get('title','')}\n\n{it['text']}")
            search.append({'kind':'law','uid':it['uid'],'reference':f"{d['code']} {it['article']}",'chapter':ch['name'],'text':it['text'],'document':'docs/current/'+slug+'.md','source':str(path.relative_to(root)).replace('\\','/')})
    register(slug,d['law'],chunks,str(path.relative_to(root)).replace('\\','/'),'docs/'+old[path.stem]+'.md' if path.stem in old else None,'law')
for path in sorted((snap/'rules').glob('*.json')):
    d=read(path);chunks=[];slug='rules-'+str(d['id'])
    for it in d['items']:
        text=it['text']
        if it.get('punish'): text+='\n\nСанкция: '+it['punish']
        chunks.append(f"## {it['ref']}\n\n{text}")
        search.append({'kind':'rule','uid':it['uid'],'reference':f"{it.get('code','')} {it['ref']}",'section':it.get('doc',''),'text':text,'document':'docs/current/'+slug+'.md','source':str(path.relative_to(root)).replace('\\','/')})
    register(slug,d['title'],chunks,str(path.relative_to(root)).replace('\\','/'),old_rules.get(str(d['id'])),'rule')

# Every remaining file remains accessible in the immutable snapshot. Provide readable
# companions for interpretative material, without promoting commentary to legislation.
refout=out/'reference';refout.mkdir(exist_ok=True)
def render(obj, depth=2):
    if isinstance(obj,dict):
        return '\n\n'.join('#'*min(depth,6)+' '+str(k)+'\n\n'+render(v,depth+1) for k,v in obj.items())
    if isinstance(obj,list):
        return '\n\n'.join(render(v,depth) for v in obj)
    return str(obj) if obj is not None else 'null'
for filename in ['dossier.json','home.json','dict.json','proc.json','penalty.json','units.json']:
    write(refout/(Path(filename).stem+'.md'), '# Справочные данные: '+filename+'\n\nМатериал приложения для изучения и поиска. Комментарии, классификация и извлечённые санкции не заменяют полный текст нормы.\n\n'+render(read(snap/filename))+'\n')
write(root/'search-current.jsonl','\n'.join(json.dumps(x,ensure_ascii=False) for x in search)+'\n')
write(root/'current-manifest.json',json.dumps({'import_date':a.date,'source_directory':str(source),'snapshot':'sources/olegha/'+a.date,'files':files,'documents':docs,'comparisons':comparisons,'legacy_mapping':mappings},ensure_ascii=False,indent=2)+'\n')
catalog='# Основная рабочая база\n\nСнимок приложения Olegha77 AI, сервер Кутузовский, от '+a.date+'. Использовать с явными поправками пользователя из AMENDMENTS.md. Не считать комментарии приложения официальным толкованием.\n\n'
catalog+='\n'.join('- ['+d['title']+']('+Path(d['path']).name+')' for d in docs)
catalog+='\n\n## Материалы для изучения\n\n'+ '\n'.join('- ['+n+'](reference/'+n+'.md)' for n in ['dossier','home','dict','proc','penalty','units'])
catalog+='\n\n## Прежние материалы без замены\n\nВоенные уставы и другие документы, отсутствующие в снимке приложения, продолжают использоваться по прежнему каталогу. Для УВС: [редакция 1de26134](../military/1de26134.md); для старых ДУ/УКПС учитывать потерю цветовой разметки.\n'
write(out/'README.md',catalog)
report='# Сверка с базой Olegha77 AI — '+a.date+'\n\nИмпортировано '+str(len(files))+' файлов без изменения байтов; '+str(len(docs))+' документов норм и '+str(len(search))+' поисковых записей.\n\nСравнения ниже являются текстовыми: различия разметки, разбивки на части, заголовков и извлечения тоже попадают в diff. Не все различия являются изменениями права. Полные исходные файлы сохранены.\n\n## Существенные ограничения\n\n- ПГО 9.9: приложение содержит 24 часа; применяется явная поправка пользователя 48 часов.\n- В тексте 9.9 приложения присутствует постороннее слово «ГИБДД»: вероятный артефакт извлечения, сохранён без исправления.\n- Справочные dossier/proc/penalty содержат трактовки и автоматически извлечённые данные; не использовать их вместо нормы. Встречаются суммы с валютой $, не переводить автоматически в рубли.\n- Дата файлов и дата импорта не доказывают официальное вступление в силу.\n- Уставы, отсутствующие в приложении, не удаляются и не заменяются пустыми материалами.\n\n## Сопоставление документов\n\n'
for c in comparisons:
    report+='### '+c['title']+'\n\n'
    if c['old']:
        report+=f"Прежний: [{c['old']}](../{c['old']}). Новый: [{c['new']}](../{c['new']}). [Полная текстовая разница](../{c['diff']}). Полностью найдено после нормализации: {c['exact_normalized_containment']} из {c['entries']} записей; низкое значение может объясняться форматированием.\n\n"
    else:report+=c['note']+' [Текст](../'+c['new']+').\n\n'
write(root/'changes'/('olegha-'+a.date+'.md'),report)
archive=root/'sources'/'previous-generated';archive.mkdir(exist_ok=True)
for name in ['ALL-LAWS.md','FAQ.md','faq-index.json']:
    dest=archive/(a.date+'-'+name)
    if (root/name).exists() and not dest.exists(): dest.write_bytes((root/name).read_bytes())
write(root/'ALL-LAWS.md','# Основные законы и правила: '+a.date+'\n\nЯвные поправки: AMENDMENTS.md. Дополнительные старые уставы — в README.md.\n\n'+'\n\n---\n\n'.join((root/d['path']).read_text(encoding='utf-8') for d in docs))
print(json.dumps({'files':len(files),'documents':len(docs),'entries':len(search),'comparisons':sum(bool(c['old']) for c in comparisons)},ensure_ascii=True))
