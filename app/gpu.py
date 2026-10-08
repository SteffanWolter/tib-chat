"""The shared GPU behind Lino and Guido. A Modal L4 that scales to zero.

state machine:  offline --wake--> waking --/health ok--> online --idle--> offline
while online a thread pings /health so Modal keeps the container. it stops pinging at `awake_until`,
then Modal scales down after its own 5 minute window (gpu/serve.py).

awake_until = max(hold chosen on the start screen, last interaction + 10 min)
Guido runs on Gemini and needs no GPU, he only shares the timer so both agents wake and sleep together.
"""
import json
import subprocess
import sys
import threading
import time
import urllib.request

import config

AWAKE_SECONDS = 10 * 60
HOLD_CHOICES = (5 * 60, 30 * 60, 60 * 60, 2 * 60 * 60, 3 * 60 * 60)  # 5 min is for testing
WAKE_TIMEOUT = 15 * 60
MODAL_APP = 'lino'
PLAN_CREDITS_USD = 30.0  # modal starter plan, $30 of free credits a month

_lock = threading.Lock()
STATE = {'status': 'offline', 'wake_started': 0.0, 'awake_until': 0.0, 'hold_s': 0, 'hold_until': 0.0,
         'cold_start_s': None, 'last_cold_start_s': 220.0}  # measured 2026-10-07: L4 + vLLM 0.28 + DSpark, 222 s


def online():
  return STATE['status'] == 'online'


def status():
  s = dict(STATE)
  now = time.time()
  s['waking_for_s'] = round(now - s['wake_started'], 1) if s['status'] == 'waking' else None
  s['awake_for_s'] = max(0, round(s['awake_until'] - now)) if s['status'] == 'online' else 0
  s['hold_for_s'] = max(0, round(s['hold_until'] - now)) if s['status'] == 'online' else 0
  s['gpu'] = 'NVIDIA L4'
  return s


def _healthy():
  try:
    with urllib.request.urlopen(config.LINO_URL + '/health', timeout=10) as r:
      return r.status == 200
  except Exception:
    return False


def _keepalive():
  while True:
    time.sleep(60)
    with _lock:
      if STATE['status'] != 'online':
        return
      if time.time() > STATE['awake_until']:
        STATE['status'] = 'offline'  # stop pinging, modal scales down on its own
        return
    if not _healthy():
      with _lock:
        STATE['status'] = 'offline'
      return


def _wait_for_boot():
  t0 = time.time()
  while time.time() - t0 < WAKE_TIMEOUT:
    if STATE['status'] != 'waking':
      return  # shut down while booting
    if _healthy():
      with _lock:
        took, now = round(time.time() - t0, 1), time.time()
        STATE.update(status='online', cold_start_s=took, hold_until=now + STATE['hold_s'],
                     awake_until=now + (STATE['hold_s'] or AWAKE_SECONDS))
        if took > 20:  # a container that was still up answers in under a second. that's not a cold start
          STATE['last_cold_start_s'] = took
      threading.Thread(target=_keepalive, daemon=True).start()
      return
    time.sleep(3)
  with _lock:
    STATE['status'] = 'offline'


def wake(hold_s=0):
  """boot the gpu, or keep it. hold_s = minimum time online, counted from the moment it's ready"""
  hold_s = min(HOLD_CHOICES, key=lambda c: abs(c - hold_s)) if hold_s else 0
  with _lock:
    if hold_s:
      STATE['hold_s'] = max(STATE['hold_s'], hold_s) if STATE['status'] == 'waking' else hold_s
    if STATE['status'] == 'online' and hold_s:
      now = time.time()
      STATE['hold_until'] = max(STATE['hold_until'], now + hold_s)
      STATE['awake_until'] = max(STATE['awake_until'], now + hold_s)
    if not config.LINO_URL or STATE['status'] in ('waking', 'online'):
      return status()
    STATE.update(status='waking', wake_started=time.time(), cold_start_s=None)
  threading.Thread(target=_wait_for_boot, daemon=True).start()
  return status()


def touch():
  """someone used lino or guido. 10 more minutes"""
  with _lock:
    if STATE['status'] == 'online':
      STATE['awake_until'] = max(STATE['awake_until'], time.time() + AWAKE_SECONDS)


def mark_offline():
  with _lock:
    STATE['status'] = 'offline'


# ---- shutting down now instead of waiting for the idle timer
def _modal(*args, check=False):
  return subprocess.run([sys.executable, '-m', 'modal', 'container', *args], capture_output=True, text=True, timeout=40, check=check).stdout


def _containers():
  return [c['container_id'] for c in json.loads(_modal('list', '--json', check=True) or '[]') if c.get('app_name') == MODAL_APP]


def _sweep():
  """modal reschedules the work of a hard stopped container once. stop the replacement too"""
  for delay in (75, 90):
    time.sleep(delay)
    if STATE['status'] != 'offline':
      return  # someone woke it again
    try:
      for cid in _containers():
        _modal('stop', cid, '--yes')
    except Exception:
      pass


def shutdown():
  """stop the containers of the modal app. the deployment stays, the next wake boots a fresh one"""
  with _lock:
    STATE.update(status='offline', awake_until=0.0, hold_until=0.0, hold_s=0)
  try:
    ids = _containers()
    for cid in ids:
      _modal('stop', cid, '--yes', check=True)
    threading.Thread(target=_sweep, daemon=True).start()
    return {'ok': True, 'stopped': len(ids), **status()}
  except Exception as e:
    return {'ok': False, 'error': type(e).__name__, **status()}


_credits = {'at': 0.0, 'data': None}


def credits():
  """share of this month's modal credits left. cached 10 minutes, the billing api is slow"""
  if _credits['data'] and time.time() - _credits['at'] < 600:
    return _credits['data']
  try:
    import modal
    s = modal.Workspace.from_context().billing.summary()
    used = float(-s.adjustments.get('Credits', 0))
    data = {'ok': True, 'used_pct': round(100 * used / PLAN_CREDITS_USD, 1),
            'remaining_pct': round(max(0.0, 100 - 100 * used / PLAN_CREDITS_USD), 1), 'resets': s.end.date().isoformat()}
  except Exception as e:
    data = {'ok': False, 'error': type(e).__name__}
  _credits.update(at=time.time(), data=data)
  return data
