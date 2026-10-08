"""MHH page export -> app/data/corpus.json.gz, the library Luna searches.

  python pipeline/build_corpus.py <clean_ready_07_10/pages> [guidelineKG.nt]

one record per page with the original OCR text (markdown and html tables kept), a readable document title from the
first heading, and an author-year reference ('McDonagh 2023') when the knowledge graph knows the document.
"""
import collections
import glob
import gzip
import json
import pathlib
import re
import sys

OUT = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'data' / 'corpus.json.gz'


def clean(t):
  t = re.sub(r'<[^>]+>', ' ', t)
  t = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', t)
  t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
  t = re.sub(r'[*_`#]+', ' ', t)
  return re.sub(r'\s+', ' ', t).strip()


def title_of(pages):
  """first markdown heading of the first two pages that looks like a title"""
  for p in pages[:2]:
    for line in p['text'].splitlines():
      if line.lstrip().startswith('#'):
        cand = clean(line)
        if 12 <= len(cand) <= 160 and not cand.lower().startswith(('table', 'figure', 'abbreviations')):
          return cand
  first = next((clean(l) for l in pages[0]['text'].splitlines() if len(clean(l)) > 8), '')
  return first[:120] or 'Guideline document'


def references(kg_path):
  """document sha256 -> 'Author 2023', parsed from the guideline slugs in the knowledge graph"""
  refs = {}
  if not kg_path or not pathlib.Path(kg_path).exists():
    return refs
  for line in open(kg_path, encoding='utf-8'):
    if 'documentSha256' not in line:
      continue
    m = re.match(r'<([^>]*)> <[^>]*> "([0-9a-f]{64})"', line)
    if not m:
      continue
    slug = m.group(1).rsplit('/', 1)[-1].split('_n0')[0]
    a = re.match(r'^([a-z]+(?:-[a-z]+)?)-(\d{4})-', slug)
    if a:
      refs[m.group(2)] = a.group(1).replace('-', ' ').title().replace(' ', '-') + ' ' + a.group(2)
  return refs


if __name__ == '__main__':
  src, kg_path = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None
  pages = []
  for f in sorted(glob.glob(src + '/*.json')):
    o = json.load(open(f, encoding='utf-8'))
    meta = o['original_page_metadata']
    pages.append({'id': o['page_id'], 'doc': meta['document_id'], 'page': meta['page_number'],
                  'text': (o.get('original_ocr') or {}).get('text') or o.get('model_input_text') or ''})
  by_doc = collections.defaultdict(list)
  for p in pages:
    by_doc[p['doc']].append(p)
  titles = {doc: title_of(sorted(ps, key=lambda p: p['page'])) for doc, ps in by_doc.items()}
  refs = references(kg_path)
  for p in pages:
    p['title'] = titles[p['doc']]
    if p['doc'] in refs:
      p['ref'] = refs[p['doc']]
  with gzip.open(OUT, 'wt', encoding='utf-8') as fh:
    json.dump({'source': 'clean_ready_07_10', 'pages': pages}, fh, ensure_ascii=False)
  print(f'{len(pages)} pages, {len(by_doc)} documents, {len(refs)} author-year refs -> {OUT} ({OUT.stat().st_size // 1024} KiB)')
