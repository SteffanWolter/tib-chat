"""Decode speed of the deployed Lino. the numbers in serve.py came from this.

  LINO_URL=... LINO_API_KEY=... python gpu/bench.py [runs]

wakes the server first if it's cold, then streams a few answers and reports tokens per second.
"""
import json
import os
import sys
import time
import urllib.request

URL = os.environ['LINO_URL'].rstrip('/')
KEY = os.environ['LINO_API_KEY']
QUESTIONS = ['What are the four pillars of HFrEF therapy?', 'What are the common side effects of ACE inhibitors?',
             'When should an ICD be considered in heart failure?', 'How does exercise training help in heart failure?']


def wait_healthy(timeout=900):
  t0 = time.time()
  while time.time() - t0 < timeout:
    try:
      if urllib.request.urlopen(URL + '/health', timeout=10).status == 200:
        return time.time() - t0
    except Exception:
      time.sleep(3)
  raise SystemExit('lino did not come up')


def run(question):
  body = {'model': 'lino', 'messages': [{'role': 'user', 'content': question}], 'stream': True, 'max_tokens': 400,
          'temperature': 0, 'stream_options': {'include_usage': True}}
  req = urllib.request.Request(URL + '/v1/chat/completions', data=json.dumps(body).encode(),
                               headers={'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
  t0, first, tokens = time.time(), None, 0
  with urllib.request.urlopen(req, timeout=120) as r:
    for raw in r:
      line = raw.decode().strip()
      if not line.startswith('data:') or line == 'data: [DONE]':
        continue
      d = json.loads(line[5:])
      if d.get('choices') and d['choices'][0]['delta'].get('content'):
        first = first or time.time()
      tokens = (d.get('usage') or {}).get('completion_tokens', tokens)
  end = time.time()
  return first - t0, tokens / (end - first)


if __name__ == '__main__':
  print(f'healthy after {wait_healthy():.0f} s')
  runs = int(sys.argv[1]) if len(sys.argv) > 1 else 2
  speeds = []
  for i in range(runs):
    for q in QUESTIONS:
      ttft, tps = run(q)
      speeds.append(tps)
      print(f'ttft {ttft:5.2f} s  {tps:6.1f} tok/s  {q}')
  print(f'median {sorted(speeds)[len(speeds) // 2]:.1f} tok/s over {len(speeds)} answers')
