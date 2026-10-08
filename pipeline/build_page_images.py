"""Rendered MHH page PNGs -> 1100 px WebP, for the page view in the source overlay.

  python pipeline/build_page_images.py <MHH-Dataset-OCR-Pipeline>
  gcloud storage cp page_images/*.webp gs://<bucket>/

input is <export>/1_rendered_pages/manifest.jsonl and its PNGs (1.6 GB). output goes to page_images/ next to app/
(443 MB, never committed). the server reads them from the private bucket, locally from page_images/.
"""
import json
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

OUT = pathlib.Path(__file__).resolve().parents[1] / 'page_images'
WIDTH = 1100


def convert(job):
  base, rec = job
  dst = OUT / (rec['page_id'] + '.webp')
  if dst.exists():
    return
  im = Image.open(base / rec['artifact_path']).convert('RGB')
  if im.width > WIDTH:
    im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
  im.save(dst, 'WEBP', quality=72, method=4)


if __name__ == '__main__':
  base = pathlib.Path(sys.argv[1])
  OUT.mkdir(exist_ok=True)
  recs = [json.loads(l) for l in open(base / '1_rendered_pages' / 'manifest.jsonl', encoding='utf-8') if l.strip()]
  with ProcessPoolExecutor(8) as pool:
    list(pool.map(convert, [(base, r) for r in recs], chunksize=20))
  total = sum(p.stat().st_size for p in OUT.glob('*.webp'))
  print(f'{len(recs)} pages -> {len(list(OUT.glob("*.webp")))} webp, {total / 1e6:.0f} MB in {OUT}')
