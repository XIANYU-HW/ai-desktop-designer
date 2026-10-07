/* Defrag 95 · 磁盘整理 95 — the cluster map, the progress bar and the Close Program list. */
(function () {
  'use strict';
  var root = document.documentElement;
  var zh = Orbit.lang === 'zh';
  root.lang = zh ? 'zh-CN' : 'en';
  if (zh) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-zh]'), function (el) { el.textContent = el.getAttribute('data-zh'); });
  }
  var T = Orbit.t;

  // ------------------------------------------------------------------ scale like a 1995 screen
  var stage = document.getElementById('stage');
  function fit() {
    var h = window.innerHeight || screen.height || 768;
    var w = window.innerWidth || screen.width || 1366;
    var z = Math.max(1, Math.min(3, Math.floor(h / 760 * 4) / 4));
    while (z > 1 && 826 * z > w * 0.62) z -= 0.25;
    root.style.setProperty('--z', String(z));
  }
  fit();
  window.addEventListener('resize', function () { fit(); sizeMap(); });

  // ------------------------------------------------------------------ cluster map
  var FREE = 0, OPT = 1, FRAG = 2, FIXED = 3, READ = 4, WRITE = 5;
  var COLORS = ['#ffffff', '#0000a8', '#00a8a8', '#a80000', '#00c000', '#ff4040'];
  var canvas = document.getElementById('map');
  var ctx = canvas.getContext('2d');
  var CELL_W = 8, CELL_H = 10, GAP = 1;
  var cols = 60, rows = 24;
  var cells = new Uint8Array(cols * rows);
  var timers = [];          // {index, until, next}
  var groups = [];          // scattered fragments, one group per loose file
  var written = [];         // groups moved into the optimized area, for undo
  var frontier = 0;
  var pendingCount = -1;
  var dirty = true;

  function rand(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function sizeMap() {
    var z = parseFloat(getComputedStyle(root).getPropertyValue('--z')) || 1;
    var dpr = Math.min(3, (window.devicePixelRatio || 1) * z);
    var cssW = canvas.clientWidth, cssH = canvas.clientHeight;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var newCols = Math.max(10, Math.floor((cssW - 6) / (CELL_W + GAP)));
    var newRows = Math.max(4, Math.floor((cssH - 6) / (CELL_H + GAP)));
    if (newCols !== cols || newRows !== rows) {
      cols = newCols; rows = newRows;
      build(Math.max(0, pendingCount));
    }
    dirty = true;
  }

  function build(pending) {
    var r = rand(1995);
    var total = cols * rows;
    cells = new Uint8Array(total);
    timers = []; groups = []; written = [];
    var usedEnd = Math.floor(total * 0.42);
    for (var i = 0; i < usedEnd; i++) cells[i] = r() < 0.9 ? OPT : FREE;
    for (var f = 0; f < total * 0.02; f++) cells[Math.floor(r() * total * 0.7)] = FIXED;
    frontier = usedEnd;
    var start = Math.floor(total * 0.5);
    for (var g = 0; g < pending; g++) {
      var size = 3 + Math.floor(r() * 5);
      var group = [];
      for (var k = 0; k < size; k++) {
        var tries = 0, index;
        do { index = start + Math.floor(r() * (total - start)); tries++; } while (cells[index] !== FREE && tries < 50);
        if (cells[index] === FREE) { cells[index] = FRAG; group.push(index); }
      }
      groups.push(group);
    }
    dirty = true;
  }

  function nextFrontier() {
    while (frontier < cells.length && cells[frontier] !== FREE) frontier++;
    return frontier < cells.length ? frontier++ : -1;
  }

  function schedule(index, temporary, finalState, ms) {
    cells[index] = temporary;
    timers.push({ index: index, until: performance.now() + ms, next: finalState });
    dirty = true;
  }

  function defragOne() {
    var group = groups.shift();
    if (!group) return;
    var moved = [];
    group.forEach(function (index, i) {
      schedule(index, READ, FREE, 260 + i * 40);
      var target = nextFrontier();
      if (target >= 0) { timers.push({ index: target, until: performance.now() + 200 + i * 40, next: WRITE, then: OPT, delay: 260 }); moved.push(target); }
    });
    written.push({ from: group, to: moved });
    blink();
  }

  function scatterOne() {
    var entry = written.pop();
    if (!entry) return;
    entry.to.forEach(function (index, i) { schedule(index, READ, FREE, 220 + i * 40); });
    entry.from.forEach(function (index, i) { timers.push({ index: index, until: performance.now() + 240 + i * 40, next: WRITE, then: FRAG, delay: 220 }); });
    frontier = Math.min.apply(null, [frontier].concat(entry.to.length ? entry.to : [frontier]));
    groups.unshift(entry.from);
    blink();
  }

  function render() {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    for (var i = 0; i < cells.length; i++) {
      var x = 3 + (i % cols) * (CELL_W + GAP), y = 3 + Math.floor(i / cols) * (CELL_H + GAP);
      var state = cells[i];
      ctx.fillStyle = COLORS[state];
      ctx.fillRect(x, y, CELL_W, CELL_H);
      if (state === FREE) { ctx.strokeStyle = '#c8c8c8'; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, CELL_W - 1, CELL_H - 1); }
      else { ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(x, y, CELL_W, 1); }
    }
  }

  var light = document.getElementById('disk-light');
  var lightTimer = 0;
  function blink() {
    light.classList.add('on');
    clearTimeout(lightTimer);
    lightTimer = setTimeout(function () { light.classList.remove('on'); }, 140);
  }

  var idleAt = 0;
  Orbit.loop(function (t) {
    var now = performance.now();
    timers = timers.filter(function (timer) {
      if (now < timer.until) return true;
      cells[timer.index] = timer.next;
      dirty = true;
      if (timer.then !== undefined) {
        timers.push({ index: timer.index, until: now + (timer.delay || 250), next: timer.then });
      }
      return false;
    });
    // idle disk activity, busier when the CPU is busier
    var cpu = (Orbit.system && Orbit.system.cpu) || 0.1;
    if (t > idleAt) {
      idleAt = t + 0.6 + (1 - cpu) * 3.5 * Math.random();
      var index = Math.floor(Math.random() * frontier);
      if (cells[index] === OPT) { schedule(index, READ, OPT, 120); blink(); }
    }
    if (dirty) { render(); dirty = false; }
  }, { fps: 20 });

  // ------------------------------------------------------------------ texts
  var fill = document.getElementById('progress-fill');
  var progressText = document.getElementById('progress-text');
  var moving = document.getElementById('moving');
  var summary = document.getElementById('frag-summary');
  function setProgress(fraction) {
    var pct = Math.round(Math.max(0, Math.min(1, fraction)) * 100);
    fill.style.width = pct + '%';
    progressText.textContent = T('完成 ' + pct + '%', pct + '% complete');
  }

  Orbit.on('status', function (e) {
    if (e.action === 'tidy-files' && e.data && typeof e.data.pending === 'number') {
      var n = e.data.pending;
      summary.textContent = n
        ? T('桌面上有 ' + n + ' 个文件需要整理', n + (n === 1 ? ' file' : ' files') + ' out of place on the desktop')
        : T('桌面没有碎片', 'The desktop is not fragmented');
      if (n !== pendingCount && !document.querySelector('[data-orbit-action="tidy-files"].is-running')) {
        pendingCount = n;
        build(n);
      }
    }
    if (e.action === 'quit-apps') refreshPrograms();
  });

  Orbit.on('action', function (e) {
    if (e.action !== 'tidy-files') return;
    if (e.phase === 'start' && (e.op === 'run' || e.op === 'undo')) { setProgress(0); moving.textContent = T('正在读取磁盘信息…', 'Reading drive information...'); }
    if (e.phase === 'progress') {
      if (typeof e.progress === 'number') setProgress(e.progress);
      if (e.status === 'moved') { defragOne(); moving.textContent = T('正在移动：', 'Moving: ') + (e.item || '') + (e.category ? ' → ' + e.category : ''); }
      if (e.status === 'restored') { scatterOne(); moving.textContent = T('正在还原：', 'Restoring: ') + (e.item || ''); }
    }
    if (e.phase === 'done' && (e.op === 'run' || e.op === 'undo')) {
      pendingCount = groups.length; // the map already shows the new state; no need to rebuild it
      setProgress(1);
      moving.textContent = e.op === 'run' ? T('桌面的碎片整理已完成。', 'Defragmentation of the desktop is complete.') : T('已撤销上一次整理。', 'The last defragmentation was undone.');
    }
  });

  document.getElementById('legend-toggle').addEventListener('click', function () {
    var legend = document.getElementById('legend');
    legend.hidden = !legend.hidden;
    setTimeout(sizeMap, 0);
  });

  // ------------------------------------------------------------------ Close Program list
  var list = document.getElementById('program-list');
  function showPrograms(apps, kept) {
    list.innerHTML = '';
    (apps || []).forEach(function (app, i) {
      var li = document.createElement('li');
      li.textContent = app.name;
      if (i === 0) li.className = 'selected';
      list.appendChild(li);
    });
    (kept || []).slice(0, 6).forEach(function (app) {
      var li = document.createElement('li');
      li.className = 'kept';
      li.textContent = app.name + T('（保留）', ' (stays open)');
      list.appendChild(li);
    });
    if (!list.children.length) {
      var empty = document.createElement('li');
      empty.className = 'kept';
      empty.textContent = T('没有正在运行的程序', 'No programs are running');
      list.appendChild(empty);
    }
  }
  var refreshing = false;
  function refreshPrograms() {
    if (refreshing || Orbit.snapshot && list.children.length) return;
    refreshing = true;
    Orbit.query('quit-apps', 'preview').then(function (result) {
      refreshing = false;
      if (result && result.ok) showPrograms(result.data.apps, result.data.kept);
    }, function () { refreshing = false; });
  }
  Orbit.on('confirm', function (e) {
    if (e.action !== 'quit-apps') return;
    if (e.phase === 'armed' && e.preview && e.preview.data) showPrograms(e.preview.data.apps, e.preview.data.kept);
  });
  Orbit.on('action', function (e) {
    if (e.action !== 'quit-apps') return;
    if (e.phase === 'progress' && e.app) {
      Array.prototype.forEach.call(list.children, function (li) {
        if (li.textContent === e.app) { li.style.textDecoration = 'line-through'; li.className = 'kept'; }
      });
    }
    if (e.phase === 'done') setTimeout(refreshPrograms, 1500);
  });
  Orbit.ready.then(function () { setInterval(refreshPrograms, 60000); });

  sizeMap();
  build(0);
})();
