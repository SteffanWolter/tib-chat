const $ = s => document.querySelector(s);
const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const H = {'X-TIB-Chat': '1', 'Content-Type': 'application/json'};
const LABEL = {visit: 'Visit', login: 'Login', login_failed: 'Wrong password', chat: 'Chat', call_start: 'Call started', call_end: 'Call ended',
  call_tool: 'Call lookup', gpu_wake: 'GPU wake', gpu_shutdown: 'GPU shut down', admin_login: 'Admin login', admin_login_failed: 'Admin: wrong password'};
const GROUPS = {All: null, Visits: ['visit', 'login', 'login_failed'], Chats: ['chat'], Calls: ['call_start', 'call_end', 'call_tool'], GPU: ['gpu_wake', 'gpu_shutdown'], Admin: ['admin_login', 'admin_login_failed']};
let EV = [], group = 'All';
function ua(s) {
  const b = /Edg\//.test(s) ? 'Edge' : /OPR\//.test(s) ? 'Opera' : /Chrome\//.test(s) ? 'Chrome' : /Firefox\//.test(s) ? 'Firefox' : /Safari\//.test(s) ? 'Safari' : s ? 'Other' : '–';
  const o = /iPhone|iPad/.test(s) ? 'iOS' : /Android/.test(s) ? 'Android' : /Windows/.test(s) ? 'Windows' : /Mac OS X/.test(s) ? 'macOS' : /Linux/.test(s) ? 'Linux' : '';
  return b + (o ? ' · ' + o : '');
}
const hue = d => { let h = 0; for (const c of d || '') h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
function detail(e) {
  if (e.kind === 'chat' || e.kind === 'call_tool') return e.text ? `<span class="txt">${esc(e.text)}</span>` : '';
  if (e.kind === 'call_end') return `${e.seconds != null ? Math.floor(e.seconds / 60) + ' min ' + (e.seconds % 60) + ' s' : ''}${e.via ? ' · ' + esc(e.via) : ''}`;
  if (e.kind === 'call_start') return `<span class="mono">${esc(e.conversation_id)}</span>`;
  if (e.kind === 'gpu_wake') return `${e.hold_min ? 'hold ' + e.hold_min + ' min' : 'wake'}${e.was ? ' · was ' + esc(e.was) : ''}`;
  if (e.kind === 'visit') return e.signed_in ? 'signed in' : 'login page';
  return '';
}
function render() {
  const q = $('#q').value.toLowerCase().trim(), kinds = GROUPS[group];
  const list = EV.filter(e => (!kinds || kinds.includes(e.kind)) && (!q || JSON.stringify(e).toLowerCase().includes(q))).slice().reverse();
  $('#rows').innerHTML = list.slice(0, 1500).map(e => {
    const t = new Date(e.ts * 1000);
    return `<tr><td class="mono">${t.toLocaleDateString('en-GB', {day: '2-digit', month: 'short'})} ${t.toLocaleTimeString('en-GB')}</td>`
      + `<td><span class="k ${e.kind}">${LABEL[e.kind] || esc(e.kind)}</span></td><td>${esc(e.agent || '')}</td><td>${detail(e)}</td>`
      + `<td class="mono">${esc(e.ip)}</td><td>${e.device ? `<span class="dev"><i style="background:oklch(0.7 0.13 ${hue(e.device)})"></i><span class="mono">${esc(e.device)}</span></span>` : '<span class="muted">–</span>'}</td>`
      + `<td>${esc(ua(e.ua))}</td></tr>`;
  }).join('') || '<tr><td colspan="7" class="muted" style="padding:30px;text-align:center">No events.</td></tr>';
}
function stats() {
  const by = k => EV.filter(e => e.kind === k), devices = new Set(EV.filter(e => e.device).map(e => e.device)), ips = new Set(EV.map(e => e.ip));
  const callSec = by('call_end').reduce((s, e) => s + (e.seconds || 0), 0);
  const chats = a => by('chat').filter(e => e.agent === a).length;
  const S = [[devices.size, 'devices'], [ips.size, 'IP addresses'], [by('login').length, 'logins'], [by('login_failed').length, 'wrong passwords'],
    [`${chats('Luna')} · ${chats('Lino')} · ${chats('Guido')}`, 'chats Luna · Lino · Guido'], [by('call_start').length, 'video calls'],
    [(callSec / 60).toFixed(1), 'call minutes (logged ends)'], [by('gpu_wake').length, 'GPU wakes']];
  $('#stats').innerHTML = S.map(([v, l]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join('');
  if (EV.length) $('#range').textContent = `${EV.length} events since ${new Date(EV[0].ts * 1000).toLocaleString('en-GB')}`;
}
async function load() {
  const r = await fetch('/api/admin/events', {cache: 'no-store'});
  if (r.status === 401) { $('#app').classList.add('hidden'); $('#login').classList.remove('hidden'); return false; }
  EV = (await r.json()).events || []; stats(); render(); return true;
}
$('#chips').innerHTML = Object.keys(GROUPS).map(g => `<button class="chip${g === group ? ' on' : ''}" data-g="${g}">${g}</button>`).join(' ');
$('#chips').onclick = e => { const b = e.target.closest('.chip'); if (!b) return; group = b.dataset.g; document.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', c === b)); render(); };
$('#q').oninput = render;
$('#login-form').onsubmit = async e => {
  e.preventDefault(); $('#err').textContent = '';
  const r = await fetch('/api/admin/login', {method: 'POST', headers: H, body: JSON.stringify({password: $('#pw').value})});
  if (!r.ok) { $('#err').textContent = 'That password is not correct.'; $('#pw').select(); return; }
  $('#pw').value = ''; start();
};
$('#logout').onclick = async () => { await fetch('/api/admin/logout', {method: 'POST', headers: H, body: '{}'}); location.reload(); };
async function start() { if (await load()) { $('#login').classList.add('hidden'); $('#app').classList.remove('hidden'); setInterval(load, 15000); } }
start();
