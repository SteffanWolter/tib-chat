"""Graph concepts -> UMLS and Wikidata ids, for the live fact cards. writes app/data/kg_links.json.gz

  python pipeline/build_kg_links.py <clean_ready_07_10>

two sources, kept apart so the ui can say where a link came from:
  kg   the normalization inside guidelineKG.nt (umls cui, wikidata qid on the entity)
  mhh  the MHH export: every mention carries top-3 retrieval candidates from UMLS 2026AA and Wikidata.
       these are candidates, not confirmed links. we take the rank-1 candidate of every mention whose surface form
       equals a concept label or alias and keep the majority vote with its support count
"""
import collections
import glob
import gzip
import json
import pathlib
import re
import sys

DATA = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'data'


def norm(text):
  """lowercase, punctuation out, plural s off: 'SGLT2 inhibitors' == 'sglt2 inhibitor'"""
  words = re.sub(r'[^a-z0-9]+', ' ', text.lower()).split()
  return ' '.join(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')) else w for w in words)


def rank1(candidates):
  return next((c for c in candidates if c.get('rank', 1) == 1), candidates[0] if candidates else None)


if __name__ == '__main__':
  graph = json.load(gzip.open(DATA / 'kg_graph.json.gz', 'rt', encoding='utf-8'))
  by_form = collections.defaultdict(set)
  for c in graph['concepts']:
    for t in [c['label']] + c.get('aliases', []):
      if len(norm(t)) > 2:
        by_form[norm(t)].add(c['id'])

  umls, wikidata, umls_meta = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter), {}
  pages = sorted(glob.glob(str(pathlib.Path(sys.argv[1]) / 'pages' / '*.json')))
  for f in pages:
    for m in json.load(open(f, encoding='utf-8')).get('mentions', []):
      ids = by_form.get(norm(m.get('surface_form', '')))
      if not ids:
        continue
      top = m.get('retrievalTop3', {})
      u = rank1((top.get('umls') or {}).get('candidates') or [])
      w = rank1((top.get('wikidata') or {}).get('candidates') or [])
      card = (u or {}).get('card') or {}
      cui = card.get('concept_id') or (u or {}).get('concept_id')
      if cui:
        name, _, rest = card.get('text', '').partition(' ( ')  # 'aspirin ( Organic Chemical : ...'
        umls_meta[cui] = {'name': name.strip(), 'type': rest.split(' :')[0].strip() if rest else '', 'release': card.get('release')}
      for cid in ids:
        if cui:
          umls[cid][cui] += 1
        if w and w.get('concept_id'):
          wikidata[cid][w['concept_id']] += 1

  out = {}
  for c in graph['concepts']:
    entry = {}
    cui, qid = (c.get('cui') or '').rsplit('/', 1)[-1] or None, (c.get('wikidata') or '').rsplit('/', 1)[-1] or None
    if cui or qid:
      entry['kg'] = {k: v for k, v in (('cui', cui), ('qid', qid)) if v}
    mhh = {}
    if umls[c['id']]:
      best, n = umls[c['id']].most_common(1)[0]
      mhh['umls'] = {'cui': best, 'support': n, 'mentions': sum(umls[c['id']].values()), **umls_meta.get(best, {})}
    if wikidata[c['id']]:
      best, n = wikidata[c['id']].most_common(1)[0]
      mhh['wikidata'] = {'qid': best, 'support': n, 'mentions': sum(wikidata[c['id']].values())}
    if mhh:
      entry['mhh'] = {**mhh, 'status': 'retrieval_top1_unconfirmed'}
    if entry:
      out[c['id']] = entry

  with gzip.open(DATA / 'kg_links.json.gz', 'wt', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
  count = lambda src, key: sum(key in v.get(src, {}) for v in out.values())
  print(f"{len(pages)} pages, {len(graph['concepts'])} concepts | kg cui {count('kg', 'cui')} qid {count('kg', 'qid')} "
        f"| mhh umls {count('mhh', 'umls')} wikidata {count('mhh', 'wikidata')} | linked {len(out)}")
