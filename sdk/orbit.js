/*!
 * Orbit Desktop SDK 0.1.0 — the bridge between a desktop theme and the local helper.
 *
 * Load it from a theme page:  <script src="../../sdk/orbit.js"></script>
 *
 * Served by the helper the page is "live": buttons run real actions. Opened any
 * other way (a file, GitHub Pages, ?demo) it runs in demo mode with sample data
 * and simulated actions, so a theme can always be previewed safely.
 *
 * Markup bindings (no JavaScript needed):
 *   data-orbit-action="tidy-files" [data-orbit-op="run"] [data-orbit-params='{"source":"downloads"}']
 *       [data-orbit-confirm="auto|always|never"]      → click runs the action
 *   data-orbit-status[="tidy-files"]                   → shows the latest message
 *   data-orbit-value="tidy-files.pending"              → a value from an action's status
 *   data-orbit-clock="{HH}:{mm}"                       → live clock (see Orbit.formatDate)
 *   data-orbit-weather="temperature|condition|high|low|place|humidity|wind"
 *   data-orbit-system="cpu|memory|disk|battery"        → percentages; also CSS vars --orbit-cpu etc. (0..1)
 *   data-orbit-gallery                                 → opens the theme gallery
 *
 * State on <html>: data-orbit-mode (live|demo), data-orbit-connection (online|offline),
 * data-orbit-paused, data-orbit-busy, data-daypart (dawn|day|dusk|night), data-weather (clear|rain|…),
 * data-os (windows|macos|linux). Element classes: is-running, is-done, is-error, is-armed, is-unavailable.
 *
 * JavaScript: Orbit.run(action, op, params) · Orbit.query(action, readOp) · Orbit.on(event, fn) · Orbit.loop(draw, {fps}) · Orbit.ready
 * Events: ready, action {action, op, phase: start|progress|done|error, progress, message, result, item},
 *         confirm {action, op, preview}, status {action, data}, weather, system, daypart, pause, resume, connection
 */
(function (global) {
  'use strict';
  if (global.Orbit) return;

  var doc = document;
  var root = doc.documentElement;
  var params = new URLSearchParams(location.search);

  function meta(name) {
    var el = doc.querySelector('meta[name="' + name + '"]');
    return el ? el.getAttribute('content') : null;
  }

  var token = meta('orbit-token');
  var live = !!token && !params.has('demo');
  var snapshot = params.has('snapshot');
  var langTag = (params.get('lang') || meta('orbit-lang') || root.getAttribute('lang') || navigator.language || 'en').toLowerCase();
  var lang = langTag.indexOf('zh') === 0 ? 'zh' : 'en';
  var themeMatch = location.pathname.match(/themes\/([^/]+)/);
  var themeId = meta('orbit-theme') || (themeMatch ? themeMatch[1] : null);
  var clientId = Math.random().toString(36).slice(2, 10);
  var platform = meta('orbit-platform') || (/Win/i.test(navigator.platform) ? 'windows' : /Mac/i.test(navigator.platform) ? 'macos' : 'linux');

  function L(zh, en) { return lang === 'zh' ? zh : en; }

  // ------------------------------------------------------------------ events
  var handlers = {};
  function on(name, fn) {
    (handlers[name] = handlers[name] || []).push(fn);
    return function () { off(name, fn); };
  }
  function off(name, fn) {
    var list = handlers[name] || [];
    var index = list.indexOf(fn);
    if (index >= 0) list.splice(index, 1);
  }
  function emit(name, detail) {
    (handlers[name] || []).slice().forEach(function (fn) {
      try { fn(detail); } catch (err) { console.error('[orbit]', name, err); }
    });
    try { doc.dispatchEvent(new CustomEvent('orbit:' + name, { detail: detail })); } catch (_) { /* old engines */ }
  }

  // ------------------------------------------------------------------ helpers
  function each(selector, fn) { Array.prototype.forEach.call(doc.querySelectorAll(selector), fn); }
  function pad(n, size) { n = String(n); while (n.length < (size || 2)) n = '0' + n; return n; }
  function getPath(obj, path) {
    return path.split('.').reduce(function (acc, key) { return acc == null ? undefined : acc[key]; }, obj);
  }
  function delay(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

  var CN_NUM = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];
  function cnNumber(n) {
    if (n <= 10) return CN_NUM[n];
    if (n < 20) return '十' + (n % 10 ? CN_NUM[n % 10] : '');
    return CN_NUM[Math.floor(n / 10)] + '十' + (n % 10 ? CN_NUM[n % 10] : '');
  }
  var SHICHEN = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
  var WEEK_ZH = ['日', '一', '二', '三', '四', '五', '六'];
  var WEEK_EN = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var MONTH_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

  /** Format a date with {YYYY} {MM} {M} {DD} {D} {HH} {H} {hh} {h} {mm} {ss} {ampm} {weekday} {wd}
   *  {month} {mon} {doy} {shichen} {cn-month} {cn-day} {cn-weekday} tokens. */
  function formatDate(d, pattern) {
    var start = new Date(d.getFullYear(), 0, 0);
    var doy = Math.floor((d - start) / 86400000);
    var h12 = d.getHours() % 12 || 12;
    var tokens = {
      'YYYY': d.getFullYear(), 'MM': pad(d.getMonth() + 1), 'M': d.getMonth() + 1,
      'DD': pad(d.getDate()), 'D': d.getDate(), 'HH': pad(d.getHours()), 'H': d.getHours(),
      'hh': pad(h12), 'h': h12, 'mm': pad(d.getMinutes()), 'ss': pad(d.getSeconds()),
      'ampm': lang === 'zh' ? (d.getHours() < 12 ? '上午' : '下午') : (d.getHours() < 12 ? 'AM' : 'PM'),
      'weekday': lang === 'zh' ? '星期' + WEEK_ZH[d.getDay()] : WEEK_EN[d.getDay()],
      'wd': lang === 'zh' ? '周' + WEEK_ZH[d.getDay()] : WEEK_EN[d.getDay()].slice(0, 3),
      'month': lang === 'zh' ? (d.getMonth() + 1) + '月' : MONTH_EN[d.getMonth()],
      'mon': lang === 'zh' ? (d.getMonth() + 1) + '月' : MONTH_EN[d.getMonth()].slice(0, 3),
      'doy': pad(doy, 3),
      'shichen': SHICHEN[Math.floor(((d.getHours() + 1) % 24) / 2)] + '时',
      'cn-month': cnNumber(d.getMonth() + 1) + '月',
      'cn-day': cnNumber(d.getDate()) + '日',
      'cn-weekday': '星期' + WEEK_ZH[d.getDay()]
    };
    return pattern.replace(/\{([a-zA-Z-]+)\}/g, function (m, key) {
      return Object.prototype.hasOwnProperty.call(tokens, key) ? tokens[key] : m;
    });
  }

  // ------------------------------------------------------------------ public object
  var Orbit = {
    version: '0.1.0',
    live: live,
    demo: !live,
    snapshot: snapshot,
    lang: lang,
    themeId: themeId,
    platform: platform,
    clientId: clientId,
    state: null,
    status: {},
    weather: null,
    system: null,
    paused: false,
    reducedMotion: false,
    pointer: { x: 0.5, y: 0.5, active: false },
    t: L,
    on: on,
    off: off,
    emit: emit,
    formatDate: formatDate
  };

  try { Orbit.reducedMotion = global.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { /* ignore */ }

  root.setAttribute('data-orbit-mode', live ? 'live' : 'demo');
  if (snapshot) {   // still images: show final states instead of half-finished transitions
    root.setAttribute('data-orbit-snapshot', '');
    var still = doc.createElement('style');
    still.textContent = '*,*::before,*::after{transition:none!important}';
    doc.head.appendChild(still);
  }
  root.setAttribute('data-os', platform);
  if (!root.getAttribute('lang')) root.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en');
  // A desktop never wants "Translate this page?": the bubble pops up in browser windows the theme opens.
  root.setAttribute('translate', 'no');
  if (!doc.querySelector('meta[name="google"]')) {
    var noTranslate = doc.createElement('meta');
    noTranslate.name = 'google';
    noTranslate.content = 'notranslate';
    doc.head.appendChild(noTranslate);
  }

  // ------------------------------------------------------------------ network
  function api(path, options) {
    options = options || {};
    var headers = { 'X-Orbit-Token': token, 'X-Orbit-Client': clientId };
    if (options.body) headers['Content-Type'] = 'application/json';
    return fetch(path, { method: options.method || 'GET', headers: headers, body: options.body, cache: 'no-store' })
      .then(function (response) {
        return response.json().catch(function () { return null; }).then(function (data) {
          if (!data) throw new Error('HTTP ' + response.status);
          return data;
        });
      });
  }

  function setConnection(online) {
    var value = online ? 'online' : 'offline';
    if (root.getAttribute('data-orbit-connection') === value) return;
    root.setAttribute('data-orbit-connection', value);
    emit('connection', { online: online });
  }

  // ------------------------------------------------------------------ demo mode
  var Demo = (function () {
    var files = L(
      ['季度报价单.xlsx', '截图 2026-10-06 21.14.png', '合同扫描件.pdf', '会议纪要.docx', '旅行照片.jpg', '新建文本文档.txt', '设计稿 v3.psd', '安装包.exe', '产品演示.mp4'],
      ['Q3 quote.xlsx', 'Screenshot 2026-10-06.png', 'Contract scan.pdf', 'Meeting notes.docx', 'Trip photo.jpg', 'New Text Document.txt', 'Poster v3.psd', 'setup.exe', 'Product demo.mp4']
    );
    var cats = L(['表格', '图片', '文档', '文档', '图片', '文档', '设计', '安装包', '视频'],
      ['Spreadsheets', 'Images', 'Documents', 'Documents', 'Images', 'Documents', 'Design', 'Installers', 'Videos']);
    var apps = ['Google Chrome', 'Microsoft Excel', L('微信', 'WeChat'), 'Visual Studio Code', 'Figma'];
    var state = { pending: files.length, undo: false, reopen: false };
    var actions = {
      'tidy-files': { id: 'tidy-files', name: L('一键收纳', 'Tidy files'), operations: { status: { effect: 'read' }, preview: { effect: 'read' }, run: { effect: 'files', undo: 'undo' }, undo: { effect: 'files' }, open: { effect: 'open' } } },
      'quit-apps': { id: 'quit-apps', name: L('一键收工', 'Wind down'), operations: { status: { effect: 'read' }, preview: { effect: 'read' }, run: { effect: 'apps', undo: 'reopen' }, reopen: { effect: 'apps' } } },
      'open-path': { id: 'open-path', name: L('打开', 'Open'), operations: { run: { effect: 'open' } } }
    };

    function progress(action, op, index, total, message, extra) {
      var detail = { action: action, op: op, phase: 'progress', progress: index / total, message: message };
      Object.keys(extra || {}).forEach(function (k) { detail[k] = extra[k]; });
      queueAction(detail);
    }

    function run(action, op, p) {
      if (action === 'tidy-files') {
        if (op === 'status') return Promise.resolve({ ok: true, data: { pending: state.pending, available: { run: state.pending > 0, undo: state.undo, open: true } } });
        if (op === 'preview') return Promise.resolve({ ok: true, message: L('将收纳 ' + state.pending + ' 个文件（演示）', 'Would file ' + state.pending + ' items (demo)'), data: { pending: state.pending } });
        if (op === 'open') return Promise.resolve({ ok: true, message: L('（演示）将打开收纳夹', '(demo) would open the archive') });
        if (op === 'run') {
          var count = state.pending;
          if (!count) return Promise.resolve({ ok: true, message: L('桌面很清爽，没有要收纳的文件。', 'Already tidy.'), data: { moved: 0 } });
          var chain = Promise.resolve();
          files.slice(0, count).forEach(function (name, i) {
            chain = chain.then(function () { return delay(260); }).then(function () {
              progress(action, op, i + 1, count, name + ' → ' + cats[i], { item: name, category: cats[i], status: 'moved' });
            });
          });
          return chain.then(function () {
            state.pending = 0; state.undo = true;
            return { ok: true, message: L('已收纳 ' + count + ' 个到「桌面收纳」（演示）', 'Filed ' + count + " into 'Desktop Archive' (demo)"), data: { moved: count, can_undo: true } };
          });
        }
        if (op === 'undo') {
          if (!state.undo) return Promise.resolve({ ok: true, message: L('没有可以撤销的收纳。', 'Nothing to undo.') });
          var back = Promise.resolve();
          files.slice().reverse().forEach(function (name, i) {
            back = back.then(function () { return delay(140); }).then(function () {
              progress(action, op, i + 1, files.length, L('放回：', 'Back: ') + name, { item: name, status: 'restored' });
            });
          });
          return back.then(function () {
            state.pending = files.length; state.undo = false;
            return { ok: true, message: L('已放回 ' + files.length + ' 个（演示）', 'Put ' + files.length + ' back (demo)') };
          });
        }
      }
      if (action === 'quit-apps') {
        if (op === 'status') return Promise.resolve({ ok: true, data: { open: state.reopen ? 0 : apps.length, available: { run: !state.reopen, reopen: state.reopen } } });
        if (op === 'preview') return Promise.resolve({ ok: true, message: L('将请 ' + apps.length + ' 个应用退出：' + apps.slice(0, 3).join('、') + ' +2', 'Will ask ' + apps.length + ' apps to quit: ' + apps.slice(0, 3).join(', ') + ' +2'), data: { apps: apps.map(function (n) { return { name: n }; }), kept: [{ name: 'Claude', reason: L('AI 工具保持运行', 'AI tools stay open') }] } });
        if (op === 'run' || op === 'reopen') {
          var chain2 = Promise.resolve();
          apps.forEach(function (name, i) {
            chain2 = chain2.then(function () { return delay(420); }).then(function () {
              progress(action, op, i + 1, apps.length, (op === 'run' ? L('已关闭：', 'Closed: ') : L('已打开：', 'Opened: ')) + name, { app: name, status: op === 'run' ? 'closed' : 'opened' });
            });
          });
          return chain2.then(function () {
            state.reopen = op === 'run';
            return { ok: true, message: op === 'run' ? L('已关闭 ' + apps.length + ' 个应用（演示）', 'Closed ' + apps.length + ' apps (demo)') : L('已重新打开 ' + apps.length + ' 个应用（演示）', 'Reopened ' + apps.length + ' apps (demo)'), data: { closed: apps.length } };
          });
        }
      }
      if (action === 'open-path') return Promise.resolve({ ok: true, message: L('（演示）将打开 ', '(demo) would open ') + ((p && p.path) || '') });
      return Promise.resolve({ ok: true, message: L('（演示）' + action + ' ' + op, '(demo) ' + action + ' ' + op) });
    }

    function weather() {
      var hour = new Date().getHours();
      return Promise.resolve({
        ok: true, demo: true, place: L('杭州', 'Lisbon'), temperature: 23, apparent: 24, humidity: 58, wind: 9,
        high: 26, low: 18, kind: 'partly', condition: L('多云', 'Partly cloudy'), is_day: hour >= 6 && hour < 18,
        sunrise: null, sunset: null, units: 'metric', hourly: []
      });
    }

    function system() {
      var t = Date.now() / 1000;
      return Promise.resolve({
        ok: true, demo: true,
        cpu: 0.28 + 0.18 * Math.sin(t / 7), memory: 0.56 + 0.05 * Math.sin(t / 23),
        disk: 0.64, battery: 0.82, charging: false
      });
    }

    return { run: run, weather: weather, system: system, actions: actions };
  })();

  // ------------------------------------------------------------------ actions
  function effectOf(action, op) {
    var meta = Orbit.state && Orbit.state.actions && Orbit.state.actions[action];
    var spec = meta && meta.operations && meta.operations[op];
    return spec ? spec.effect : 'read';
  }
  function hasOp(action, op) {
    var meta = Orbit.state && Orbit.state.actions && Orbit.state.actions[action];
    return !!(meta && meta.operations && meta.operations[op]);
  }

  function call(action, op, p) {
    if (!live) return Demo.run(action, op, p || {});
    return api('/api/actions/' + encodeURIComponent(action) + '/' + encodeURIComponent(op), {
      method: 'POST', body: JSON.stringify({ params: p || {} })
    });
  }

  var lastMessages = {};
  function setMessage(action, message) {
    if (!message) return;
    lastMessages[action || '*'] = message;
    each('[data-orbit-status]', function (el) {
      var filter = el.getAttribute('data-orbit-status');
      if (!filter || filter === action) el.textContent = message;
    });
    emit('message', { action: action, message: message });
  }

  function setBusy(action, op, busy) {
    each('[data-orbit-action="' + action + '"]', function (el) {
      if ((el.getAttribute('data-orbit-op') || 'run') === op) el.classList.toggle('is-running', busy);
    });
    var running = doc.querySelectorAll('[data-orbit-action].is-running');
    if (running.length) root.setAttribute('data-orbit-busy', action);
    else root.removeAttribute('data-orbit-busy');
  }

  function flash(el, cls) {
    el.classList.remove('is-done', 'is-error');
    el.classList.add(cls);
    setTimeout(function () { el.classList.remove(cls); }, 2600);
  }

  // Action events are paced so a run that finishes in a blink still animates one item at a time.
  var actionQueue = [];
  var pumping = false;
  Orbit.progressPace = 160;
  function queueAction(detail) {
    actionQueue.push(detail);
    if (!pumping) pump();
  }
  function pump() {
    if (!actionQueue.length) { pumping = false; return; }
    pumping = true;
    var detail = actionQueue.shift();
    if (detail.before) { try { detail.before(); } catch (_) { /* keep going */ } delete detail.before; }
    emit('action', detail);
    if (detail.phase === 'progress' && detail.message) setMessage(detail.action, detail.message);
    if (detail.after) { try { detail.after(); } catch (_) { /* keep going */ } delete detail.after; }
    setTimeout(pump, detail.phase === 'progress' ? Orbit.progressPace : 0);
  }

  /** Run an action operation. Resolves to {ok, message, data} once its animation events have played. */
  function run(action, op, p) {
    op = op || 'run';
    queueAction({ action: action, op: op, phase: 'start', local: true });
    setBusy(action, op, true);
    return call(action, op, p).catch(function () {
      return { ok: false, message: live ? L('桌面助手没有响应，请确认它在运行。', 'The desktop helper is not responding.') : L('演示出错', 'Demo error') };
    }).then(function (result) {
      if (!result || typeof result !== 'object') result = { ok: false, message: L('没有收到结果', 'No result') };
      return new Promise(function (resolve) {
        queueAction({
          action: action, op: op, phase: result.ok ? 'done' : 'error', result: result, message: result.message, local: true,
          before: function () { setBusy(action, op, false); },
          after: function () {
            setMessage(action, result.message);
            if (op !== 'status' && op !== 'preview') refreshStatus(action);
            resolve(result);
          }
        });
      });
    });
  }
  Orbit.run = run;

  /** Ask a read-only operation (such as 'preview' or 'status') for data without touching the UI:
   *  no busy state, no messages, no action events. Resolves to {ok, message, data}. */
  Orbit.query = function (action, op, p) {
    if (!hasOp(action, op || 'status')) return Promise.resolve({ ok: false, message: 'unknown operation', data: {} });
    if (effectOf(action, op || 'status') !== 'read') return Promise.reject(new Error('Orbit.query only runs read-only operations'));
    return call(action, op || 'status', p || {}).catch(function () { return { ok: false, data: {} }; });
  };

  // Confirmation for operations that close apps or change settings: the first
  // click arms the button and shows what will happen; a second click runs it.
  var ARM_MS = 7000;
  var armed = null;
  function needsConfirm(el, action, op) {
    var mode = el.getAttribute('data-orbit-confirm') || 'auto';
    if (mode === 'always') return true;
    if (mode === 'never') return false;
    var effect = effectOf(action, op);
    return effect === 'apps' || effect === 'system';
  }
  function disarm() {
    if (!armed) return;
    armed.el.classList.remove('is-armed');
    clearTimeout(armed.timer);
    var action = armed.action;
    armed = null;
    setMessage(action, L('已取消', 'Cancelled'));
    emit('confirm', { action: action, phase: 'cancel' });
  }
  function arm(el, action, op, p) {
    disarm();
    el.classList.add('is-armed');
    armed = { el: el, action: action, op: op, timer: setTimeout(disarm, ARM_MS) };
    var hint = L(' · 再点一次确认', ' · click again to confirm');
    var preview = hasOp(action, 'preview') && op === 'run' ? call(action, 'preview', p) : Promise.resolve(null);
    return preview.then(function (result) {
      if (!armed || armed.el !== el) return;
      setMessage(action, ((result && result.message) || L('确认要执行吗？', 'Are you sure?')) + hint);
      emit('confirm', { action: action, op: op, phase: 'armed', preview: result });
    }).catch(function () { setMessage(action, L('确认要执行吗？', 'Are you sure?') + hint); });
  }

  doc.addEventListener('click', function (event) {
    var el = event.target.closest ? event.target.closest('[data-orbit-action],[data-orbit-gallery]') : null;
    if (!el) { disarm(); return; }
    event.preventDefault();
    if (el.hasAttribute('data-orbit-gallery')) {
      if (live) api('/api/gallery/open', { method: 'POST', body: '{}' }).catch(function () {});
      return;
    }
    if (el.classList.contains('is-running') || el.getAttribute('aria-disabled') === 'true') return;
    var action = el.getAttribute('data-orbit-action');
    var op = el.getAttribute('data-orbit-op') || 'run';
    var p = {};
    try { p = JSON.parse(el.getAttribute('data-orbit-params') || '{}'); } catch (_) { p = {}; }
    if (needsConfirm(el, action, op) && !(armed && armed.el === el)) { arm(el, action, op, p); return; }
    if (armed && armed.el === el) { clearTimeout(armed.timer); el.classList.remove('is-armed'); armed = null; }
    run(action, op, p).then(function (result) { flash(el, result.ok ? 'is-done' : 'is-error'); });
  });

  // ------------------------------------------------------------------ status of actions
  function applyStatus(action, data) {
    Orbit.status[action] = data || {};
    var available = (data && data.available) || {};
    each('[data-orbit-action="' + action + '"]', function (el) {
      var op = el.getAttribute('data-orbit-op') || 'run';
      var off = available[op] === false;
      el.classList.toggle('is-unavailable', off);
      if (off) el.setAttribute('aria-disabled', 'true'); else el.removeAttribute('aria-disabled');
    });
    each('[data-orbit-value^="' + action + '."]', function (el) {
      var value = getPath(data || {}, el.getAttribute('data-orbit-value').slice(action.length + 1));
      if (value === undefined || value === null) { el.setAttribute('data-orbit-empty', ''); el.textContent = ''; }
      else { el.removeAttribute('data-orbit-empty'); el.textContent = String(value); }
    });
    emit('status', { action: action, data: data || {} });
  }

  function refreshStatus(action) {
    if (!hasOp(action, 'status')) return Promise.resolve();
    return call(action, 'status', {}).then(function (result) {
      if (result && result.ok) applyStatus(action, result.data);
    }).catch(function () {});
  }

  function usedActions() {
    var ids = {};
    each('[data-orbit-action]', function (el) { ids[el.getAttribute('data-orbit-action')] = true; });
    each('[data-orbit-value]', function (el) { ids[el.getAttribute('data-orbit-value').split('.')[0]] = true; });
    return Object.keys(ids);
  }

  function refreshAllStatus() {
    return Promise.all(usedActions().map(refreshStatus));
  }

  // ------------------------------------------------------------------ clock, daypart
  function tickClock() {
    var now = new Date();
    each('[data-orbit-clock]', function (el) {
      var text = formatDate(now, el.getAttribute('data-orbit-clock') || '{HH}:{mm}');
      if (el.textContent !== text) el.textContent = text;
    });
  }

  function minutesOf(value) {
    if (!value) return null;
    var m = String(value).match(/T(\d{2}):(\d{2})/);
    return m ? parseInt(m[1], 10) * 60 + parseInt(m[2], 10) : null;
  }

  function updateDaypart() {
    var now = new Date();
    var minutes = now.getHours() * 60 + now.getMinutes();
    var rise = minutesOf(Orbit.weather && Orbit.weather.sunrise);
    var set = minutesOf(Orbit.weather && Orbit.weather.sunset);
    if (rise == null) rise = 6 * 60 + 30;
    if (set == null) set = 18 * 60 + 30;
    var forced = params.get('daypart');
    var part = forced || (minutes < rise - 40 || minutes > set + 50 ? 'night'
      : minutes < rise + 50 ? 'dawn'
        : minutes > set - 60 ? 'dusk' : 'day');
    if (root.getAttribute('data-daypart') !== part) {
      root.setAttribute('data-daypart', part);
      Orbit.daypart = part;
      emit('daypart', { daypart: part });
    }
  }

  // ------------------------------------------------------------------ weather
  function formatTemp(value) { return (value === null || value === undefined) ? '' : Math.round(value) + '°'; }

  function applyWeather(w) {
    Orbit.weather = w;
    var forced = params.get('weather');
    var kind = forced || (w && w.ok ? w.kind : null);
    if (kind) root.setAttribute('data-weather', kind); else root.removeAttribute('data-weather');
    each('[data-orbit-weather]', function (el) {
      var field = el.getAttribute('data-orbit-weather');
      var value = '';
      if (w && w.ok) {
        if (field === 'temperature' || field === 'high' || field === 'low' || field === 'apparent') value = formatTemp(w[field]);
        else if (field === 'humidity') value = w.humidity == null ? '' : Math.round(w.humidity) + '%';
        else if (field === 'wind') value = w.wind == null ? '' : Math.round(w.wind) + (w.units === 'imperial' ? ' mph' : ' km/h');
        else value = w[field] == null ? '' : String(w[field]);
      }
      if (value) el.removeAttribute('data-orbit-empty'); else el.setAttribute('data-orbit-empty', '');
      el.textContent = value;
    });
    updateDaypart();
    emit('weather', w);
  }

  function refreshWeather() {
    var source = live ? api('/api/weather') : Demo.weather();
    return source.then(applyWeather).catch(function () { applyWeather(null); });
  }

  // ------------------------------------------------------------------ system
  function percent(value) { return (value === null || value === undefined) ? '' : Math.round(value * 100) + '%'; }

  function applySystem(s) {
    Orbit.system = s;
    ['cpu', 'memory', 'disk', 'battery'].forEach(function (key) {
      var value = s ? s[key] : null;
      if (value === null || value === undefined) root.style.removeProperty('--orbit-' + key);
      else root.style.setProperty('--orbit-' + key, String(Math.round(value * 1000) / 1000));
    });
    each('[data-orbit-system]', function (el) {
      var key = el.getAttribute('data-orbit-system');
      var text = s ? percent(s[key]) : '';
      if (text) el.removeAttribute('data-orbit-empty'); else el.setAttribute('data-orbit-empty', '');
      el.textContent = text;
    });
    emit('system', s);
  }

  function refreshSystem() {
    if (Orbit.paused && !snapshot) return Promise.resolve();
    var source = live ? api('/api/system') : Demo.system();
    return source.then(applySystem).catch(function () {});
  }

  // ------------------------------------------------------------------ pause & animation
  var pauseReasons = {};
  function setPaused(reason, value) {
    if (value) pauseReasons[reason] = true; else delete pauseReasons[reason];
    var paused = Object.keys(pauseReasons).length > 0;
    if (paused === Orbit.paused) return;
    Orbit.paused = paused;
    root.setAttribute('data-orbit-paused', paused ? 'true' : 'false');
    emit(paused ? 'pause' : 'resume', {});
  }
  doc.addEventListener('visibilitychange', function () { setPaused('hidden', doc.hidden); });
  // Lively Wallpaper calls this when the wallpaper is covered by a full-screen app.
  global.livelyWallpaperPlaybackChanged = function (data) {
    try {
      var value = typeof data === 'string' ? JSON.parse(data) : data;
      setPaused('lively', !!(value && value.IsPaused));
    } catch (_) { /* ignore malformed calls */ }
  };

  /** Run draw(t, dt) at most `fps` times a second. Stops while the desktop is hidden or covered;
   *  t keeps counting seconds of visible animation, so nothing jumps when it resumes. */
  function loop(draw, options) {
    options = options || {};
    var fps = Math.max(1, Math.min(60, options.fps || 30));
    var slowFps = options.reducedFps || 2;
    var last = 0, elapsed = 0, raf = 0, stopped = false;
    function frame(now) {
      raf = 0;
      if (stopped || Orbit.paused) return;
      var limit = 1000 / (Orbit.reducedMotion ? Math.min(fps, slowFps) : fps);
      if (last && now - last < limit - 2) { raf = requestAnimationFrame(frame); return; }
      var dt = last ? Math.min(0.1, (now - last) / 1000) : 1 / fps;
      last = now;
      elapsed += dt;
      try { draw(elapsed, dt); } catch (err) { console.error('[orbit] draw', err); }
      raf = requestAnimationFrame(frame);
    }
    function start() { if (!raf && !stopped) { last = 0; raf = requestAnimationFrame(frame); } }
    var offResume = on('resume', start);
    start();
    return {
      stop: function () { stopped = true; if (raf) cancelAnimationFrame(raf); offResume(); },
      get time() { return elapsed; }
    };
  }
  Orbit.loop = loop;

  global.addEventListener('pointermove', function (e) {
    Orbit.pointer.x = e.clientX / Math.max(1, global.innerWidth);
    Orbit.pointer.y = e.clientY / Math.max(1, global.innerHeight);
    Orbit.pointer.active = true;
  }, { passive: true });
  global.addEventListener('pointerleave', function () { Orbit.pointer.active = false; });

  // ------------------------------------------------------------------ live connection
  var events = null;
  function connectEvents() {
    if (!live || snapshot || events || typeof EventSource === 'undefined') return;
    events = new EventSource('/api/events?token=' + encodeURIComponent(token) + '&client=' + clientId);
    events.addEventListener('hello', function () { setConnection(true); });
    events.onerror = function () { setConnection(false); };
    events.addEventListener('action', function (message) {
      var detail;
      try { detail = JSON.parse(message.data); } catch (_) { return; }
      var mine = detail.client === clientId;
      if (detail.phase === 'progress') { queueAction(detail); return; }
      if (mine) return; // this page already reported its own start and finish
      detail.local = false;
      if (detail.result) detail.message = detail.result.message;
      if (detail.phase !== 'start') {
        detail.after = function () {
          if (detail.message) setMessage(detail.action, detail.message);
          refreshStatus(detail.action);
        };
      }
      queueAction(detail);
    });
    events.addEventListener('theme-updated', function (message) {
      try { if (JSON.parse(message.data).id === themeId) location.reload(); } catch (_) { /* ignore */ }
    });
    events.addEventListener('theme-changed', function (message) {
      try {
        var id = JSON.parse(message.data).id;
        if (params.has('live') && id !== themeId) location.replace('/');
      } catch (_) { /* ignore */ }
    });
  }

  var readyResolve;
  Orbit.ready = new Promise(function (resolve) { readyResolve = resolve; });

  function loadState() {
    if (!live) {
      Orbit.state = { app: 'orbit-desktop', demo: true, language: lang, actions: Demo.actions, active_theme: themeId };
      return Promise.resolve(Orbit.state);
    }
    return api('/api/state').then(function (state) {
      Orbit.state = state;
      setConnection(true);
      return state;
    });
  }

  function start() {
    tickClock();
    setInterval(tickClock, 1000);
    updateDaypart();
    setInterval(updateDaypart, 60000);
    var attempt = function () {
      loadState().then(function () {
        connectEvents();
        return Promise.all([refreshAllStatus(), refreshWeather(), refreshSystem()]);
      }).then(function () {
        readyResolve(Orbit);
        emit('ready', Orbit);
        if (!snapshot) {
          setInterval(refreshSystem, 5000);
          setInterval(refreshWeather, 20 * 60000);
          setInterval(refreshAllStatus, 60000);
        }
      }).catch(function () {
        setConnection(false);
        setTimeout(attempt, 4000); // the helper may still be starting after sign-in
      });
    };
    attempt();
  }

  // ------------------------------------------------------------------ review (orbit.py review)
  // With ?review the page measures itself after a few seconds and writes a JSON report into the DOM,
  // which `orbit.py review` reads through a headless browser: fonts that did not load, text set in a
  // fallback font, overlapping controls, tiny text, text under the desktop icons or the taskbar,
  // script errors and resources fetched from the network.
  function fontAvailable(family) {
    var probe = doc.createElement('canvas').getContext('2d');
    var sample = 'mmmmmmmmmmlli永字八法WwQq0123';
    return ['monospace', 'serif', 'sans-serif'].some(function (generic) {
      probe.font = '72px ' + generic;
      var base = probe.measureText(sample).width;
      probe.font = '72px "' + family + '", ' + generic;
      return probe.measureText(sample).width !== base;
    });
  }

  function writeReview(errors) {
    var vw = global.innerWidth, vh = global.innerHeight;
    var report = { viewport: [vw, vh], state: root.getAttribute('data-review-state'), platform: platform, errors: errors.slice(0, 30), fonts: [], families: {}, text: [],
      overlaps: [], zones: [], offscreen: [], network: [], translate: root.getAttribute('translate') === 'no' };
    if (doc.fonts && doc.fonts.forEach) {
      doc.fonts.forEach(function (f) { report.fonts.push({ family: f.family.replace(/["']/g, ''), weight: f.weight, style: f.style, status: f.status }); });
    }
    var safeLeft = platform === 'windows' ? 112 : 0, safeRight = platform === 'macos' ? 118 : 0, taskbar = vh * 0.94;
    var stackCache = {};
    function visible(el) {
      var cs = global.getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') return false;
      for (var n = el; n && n !== root; n = n.parentElement) {
        if (parseFloat(global.getComputedStyle(n).opacity) < 0.05) return false;
      }
      var r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }
    function label(el) {
      var cls = typeof el.className === 'string' && el.className ? '.' + el.className.split(/\s+/)[0] : el.tagName.toLowerCase();
      return cls + ' "' + (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 24) + '"';
    }
    each('body *', function (el) {
      if (/^(SCRIPT|STYLE|CANVAS|SVG)$/i.test(el.tagName)) return;
      var own = Array.prototype.some.call(el.childNodes, function (n) { return n.nodeType === 3 && n.textContent.trim(); });
      if (!own || !visible(el)) return;
      var cs = global.getComputedStyle(el), r = el.getBoundingClientRect(), size = parseFloat(cs.fontSize);
      // A stack such as "KaiTi", "STKaiti", "Kaiti SC", serif is fine when any named font exists:
      // report the one that is actually used, and flag the stack only when all of them are missing.
      var stack = cs.fontFamily.split(',').map(function (f) { return f.trim().replace(/["']/g, ''); }).filter(function (f) {
        return f && !/^(serif|sans-serif|monospace|system-ui|cursive|fantasy|ui-[a-z-]+|-apple-system|BlinkMacSystemFont)$/i.test(f);
      });
      var family = stack.length ? stack[0] : cs.fontFamily;
      for (var s = 0; s < stack.length; s++) {
        if (stackCache[stack[s]] === undefined) stackCache[stack[s]] = fontAvailable(stack[s]);
        if (stackCache[stack[s]]) { family = stack[s]; break; }
      }
      if (!Object.prototype.hasOwnProperty.call(report.families, family)) report.families[family] = stack.length ? !!stackCache[family] : true;
      report.text.push({ el: label(el), size: Math.round(size * 10) / 10, family: family, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] });
      if (r.left < safeLeft || r.right > vw - safeRight) report.zones.push({ el: label(el), zone: 'desktop icons' });
      if (r.bottom > taskbar) report.zones.push({ el: label(el), zone: 'taskbar / Dock' });
      if (r.left < -1 || r.top < -1 || r.right > vw + 1 || r.bottom > vh + 1) report.offscreen.push(label(el));
    });
    var controls = [];
    each('[data-orbit-action],[data-orbit-gallery],button,input,textarea,select,[data-orbit-clock],[data-orbit-status]', function (el) {
      if (visible(el)) controls.push(el);
    });
    for (var i = 0; i < controls.length; i++) {
      for (var j = i + 1; j < controls.length; j++) {
        if (controls[i].contains(controls[j]) || controls[j].contains(controls[i])) continue;
        var a = controls[i].getBoundingClientRect(), b = controls[j].getBoundingClientRect();
        var w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (w > 2 && h > 2) report.overlaps.push([label(controls[i]), label(controls[j])]);
      }
    }
    try {
      performance.getEntriesByType('resource').forEach(function (entry) {
        var host = new URL(entry.name).hostname;
        if (host && host !== location.hostname && host !== '127.0.0.1' && host !== 'localhost') report.network.push(entry.name.slice(0, 140));
      });
    } catch (_) { /* old engines */ }
    var out = doc.createElement('script');
    out.type = 'application/json';
    out.id = 'orbit-review';
    out.textContent = JSON.stringify(report).replace(/</g, '\\u003c');
    doc.body.appendChild(out);
  }

  if (params.has('review')) {
    var reviewErrors = [];
    global.addEventListener('error', function (e) { reviewErrors.push(String(e.message || e)); });
    global.addEventListener('unhandledrejection', function (e) { reviewErrors.push('promise: ' + String((e.reason && e.reason.message) || e.reason)); });
    var consoleError = console.error;
    console.error = function () {
      reviewErrors.push(Array.prototype.join.call(arguments, ' '));
      return consoleError.apply(console, arguments);
    };
    setTimeout(function () { writeReview(reviewErrors); }, Number(params.get('review')) || 3500);
  }

  global.Orbit = Orbit;
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start);
  else start();
})(window);
