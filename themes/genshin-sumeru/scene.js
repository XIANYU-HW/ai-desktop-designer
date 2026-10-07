/* Sumeru · Garden of Knowledge. Original elemental interpretation, not combat simulation. */
(function () {
  'use strict';
  var root = document.documentElement, params = new URLSearchParams(location.search);
  var zh = Orbit.lang === 'zh', snapshot = params.has('snapshot'), fixture = params.get('review-state');
  var $ = function (id) { return document.getElementById(id); };
  var text = function (cn, en) { return zh ? cn : en; };
  root.lang = zh ? 'zh-CN' : 'en';
  document.title = text('须弥 · 知识之庭', 'Sumeru · Garden of Knowledge');
  if (!zh) {
    document.querySelectorAll('[data-en]').forEach(function (el) { el.textContent = el.dataset.en; });
    document.querySelectorAll('[data-en-label]').forEach(function (el) { el.setAttribute('aria-label', el.dataset.enLabel); });
    document.querySelectorAll('[data-en-clock]').forEach(function (el) { el.setAttribute('data-orbit-clock', el.dataset.enClock); });
    document.querySelectorAll('[data-en-placeholder]').forEach(function (el) { el.placeholder = el.dataset.enPlaceholder; });
  }

  // Notes stay in the local browser. Demo storage is separate from the live desktop.
  var noteKey = 'orbit-sumeru-leaf-notes-v1' + (Orbit.demo ? '-demo' : ''), storageOK = true;
  var note = $('note-text');
  try { if (!(Orbit.demo && fixture)) note.value = localStorage.getItem(noteKey) || ''; }
  catch (error) { storageOK = false; }
  function noteSummary(saved) {
    var length = note.value.length;
    $('note-count').textContent = length ? length + (storageOK ? text(' 字 · 已留存', ' chars · kept') : text(' 字 · 未保存', ' chars · unsaved')) : text('留一行灵感', 'Keep a thought');
    $('note-saved').textContent = storageOK
      ? (saved ? text('已保存 · 仅在此浏览器', 'Saved · this browser only') : text('仅保存在此浏览器', 'Stored in this browser only'))
      : text('暂不能保存；请先复制内容', 'Storage unavailable; copy your note');
  }
  function saveNote() {
    if (Orbit.demo && fixture) { $('note-saved').textContent = text('演示便笺 · 不保存此样例', 'Demo note · sample is not saved'); return; }
    try { localStorage.setItem(noteKey, note.value); storageOK = true; }
    catch (error) { storageOK = false; }
    noteSummary(true);
  }
  function openNotes(open, focus) {
    $('note-panel').hidden = !open;
    $('note-toggle').setAttribute('aria-expanded', String(open));
    if (open && focus) note.focus();
  }
  $('note-toggle').addEventListener('click', function () { openNotes($('note-panel').hidden, true); });
  $('note-close').addEventListener('click', function () { saveNote(); openNotes(false); $('note-toggle').focus(); });
  $('note-clear').addEventListener('click', function () { note.value = ''; saveNote(); note.focus(); });
  note.addEventListener('input', saveNote);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !$('note-panel').hidden) { saveNote(); openNotes(false); $('note-toggle').focus(); }
  });
  window.addEventListener('pagehide', saveNote);
  noteSummary(false);

  // The painted city stays static. Only small, image-aligned water/leaf/light layers are drawn.
  var canvas = $('living-garden'), ctx = canvas.getContext('2d');
  var W = 1, H = 1, DPR = 1, box, elapsed = 0, animation = null, frames = 0;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var element = 'dendro', reactions = [], pointer = { active: false, x: 0, y: 0 };
  var colors = { dendro: [178, 222, 122], hydro: [132, 226, 236], electro: [206, 163, 249] };
  var water = [
    { x: .370, y: .451, w: .029, h: .075 },
    { x: .594, y: .507, w: .012, h: .106 },
    { x: .657, y: .574, w: .019, h: .100 },
    { x: .719, y: .576, w: .015, h: .087 },
    { x: .710, y: .692, w: .025, h: .075 }
  ];
  function rgba(rgb, a) { return 'rgba(' + rgb.join(',') + ',' + Math.max(0, Math.min(1, a)) + ')'; }
  function imagePoint(u, v) {
    // Same cover transform as .art; normalized positions refer to the 16:9 background artwork.
    var scale = Math.max(innerWidth / 1672, innerHeight / 941);
    return { x: u * 1672 * scale + (innerWidth - 1672 * scale) / 2 - box.left,
      y: v * 941 * scale + (innerHeight - 941 * scale) / 2 - box.top,
      scale: scale };
  }
  function centerPoint() {
    var r = $('resonance-point').getBoundingClientRect();
    return { x: r.left + r.width / 2 - box.left, y: r.top + r.height / 2 - box.top };
  }
  function resize() {
    box = canvas.getBoundingClientRect(); W = box.width; H = box.height;
    DPR = Math.min(devicePixelRatio || 1, 1.5, 1400 / Math.max(W, H));
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    draw(elapsed, 0);
  }
  function leafShape(length, width) {
    ctx.beginPath(); ctx.moveTo(0, -length / 2);
    ctx.bezierCurveTo(width, -length / 5, width, length / 3, 0, length / 2);
    ctx.bezierCurveTo(-width / 2, length / 5, -width / 2, -length / 3, 0, -length / 2);
  }
  function ambient(t) {
    // Narrow traveling highlights follow the actual falls, rather than a screen-wide water shader.
    water.forEach(function (fall, index) {
      var p = imagePoint(fall.x, fall.y), width = fall.w * 1672 * p.scale, height = fall.h * 941 * p.scale;
      ctx.save(); ctx.beginPath(); ctx.rect(p.x, p.y, width, height); ctx.clip();
      for (var j = 0; j < 5; j++) {
        var phase = (t * (.18 + index * .015) + j * .217) % 1;
        var x = p.x + width * (.12 + .17 * j) + Math.sin(t * .7 + j) * 1.2;
        var y = p.y + height * phase;
        var glow = ctx.createLinearGradient(0, y - 15, 0, y + 17);
        glow.addColorStop(0, 'rgba(192,241,237,0)');
        glow.addColorStop(.55, 'rgba(223,250,236,.25)'); glow.addColorStop(1, 'rgba(192,241,237,0)');
        ctx.strokeStyle = glow; ctx.lineWidth = 1.6 * p.scale; ctx.beginPath();
        ctx.moveTo(x, y - 15); ctx.quadraticCurveTo(x - 1.5, y, x + 1, y + 17); ctx.stroke();
      }
      ctx.restore();
    });
    var pool = imagePoint(.673, .790);
    for (var ring = 0; ring < 3; ring++) {
      var pulse = (t * .14 + ring / 3) % 1;
      ctx.strokeStyle = 'rgba(169,231,217,' + ((1 - pulse) * .17) + ')'; ctx.lineWidth = .8;
      ctx.beginPath(); ctx.ellipse(pool.x, pool.y + ring * 3, (22 + pulse * 67) * pool.scale, (3 + pulse * 8) * pool.scale, -.09, 0, Math.PI * 2); ctx.stroke();
    }
    // A handful of leaf reflections stay near the right-hand canopy and garden, never over the tools.
    for (var i = 0; i < 7; i++) {
      var u = .59 + (i * .047) % .30 + Math.sin(t * .08 + i) * .012;
      var v = .18 + (i * .091 + t * .004) % .48;
      var lp = imagePoint(u, v);
      ctx.save(); ctx.translate(lp.x, lp.y); ctx.rotate(i * .8 + Math.sin(t * .22 + i) * .4);
      leafShape(6 + (i % 3) * 3, 3); ctx.fillStyle = 'rgba(183,211,113,.28)'; ctx.fill();
      ctx.restore();
    }
    for (var dust = 0; dust < 12; dust++) {
      var dp = imagePoint(.58 + .28 * ((dust * .618) % 1), .25 + .40 * ((dust * .382) % 1));
      dp.x += Math.sin(t * .17 + dust) * 9; dp.y += Math.cos(t * .11 + dust * .4) * 7;
      var opacity = .14 + .11 * Math.sin(t * .5 + dust);
      ctx.fillStyle = 'rgba(247,221,143,' + opacity + ')'; ctx.beginPath(); ctx.arc(dp.x, dp.y, dust % 3 === 0 ? 1.4 : .8, 0, Math.PI * 2); ctx.fill();
    }
    if (pointer.active) {
      var aura = ctx.createRadialGradient(pointer.x, pointer.y, 1, pointer.x, pointer.y, 66);
      aura.addColorStop(0, rgba(colors[element], .11)); aura.addColorStop(1, rgba(colors[element], 0));
      ctx.fillStyle = aura; ctx.fillRect(pointer.x - 66, pointer.y - 66, 132, 132);
    }
  }
  function petal(radius, width, rgb, alpha) {
    ctx.beginPath(); ctx.moveTo(0, 3);
    ctx.bezierCurveTo(width, -radius * .23, width * .83, -radius * .72, 0, -radius);
    ctx.bezierCurveTo(-width * .8, -radius * .72, -width, -radius * .23, 0, 3);
    var fill = ctx.createLinearGradient(0, 0, 0, -radius);
    fill.addColorStop(0, rgba(rgb, alpha * .02)); fill.addColorStop(.72, rgba(rgb, alpha * .13)); fill.addColorStop(1, rgba([244,230,162], alpha * .27));
    ctx.fillStyle = fill; ctx.fill();
    ctx.strokeStyle = rgba([21, 83, 74], alpha * .50); ctx.lineWidth = 3; ctx.stroke();
    ctx.strokeStyle = rgba(rgb, alpha * .92); ctx.lineWidth = 1.05; ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.quadraticCurveTo(3, -radius * .45, 0, -radius * .91);
    ctx.strokeStyle = rgba([226,226,156], alpha * .53); ctx.lineWidth = .8; ctx.stroke();
  }
  function drawBloom(effect, p) {
    var alpha = Math.sin(Math.PI * Math.min(1, p)) * .87;
    var radius = (40 + Math.sin(p * Math.PI / 2) * 147) * Math.min(1.2, innerHeight / 900);
    var rgb = colors[effect.type], angle = effect.type === 'hydro' ? .15 : -.08;
    ctx.save(); ctx.translate(effect.x, effect.y); ctx.rotate(angle * p);
    var veil = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 1.15);
    veil.addColorStop(0, 'rgba(4,45,30,' + alpha * .16 + ')'); veil.addColorStop(1, 'rgba(4,45,30,0)');
    ctx.fillStyle = veil; ctx.fillRect(-radius * 1.15, -radius * 1.15, radius * 2.3, radius * 2.3);
    for (var layer = 0; layer < 2; layer++) {
      var petals = layer ? 6 : 12;
      for (var j = 0; j < petals; j++) {
        ctx.save(); ctx.rotate(j * Math.PI * 2 / petals + (layer ? Math.PI / 6 : 0));
        petal(radius * (layer ? .61 : 1), radius * (layer ? .22 : .20), layer ? [192,226,125] : rgb, alpha * (layer ? .95 : .8));
        ctx.restore();
      }
    }
    for (var ring = 0; ring < 3; ring++) {
      var r = radius * (.70 + ring * .20 + p * .2);
      ctx.strokeStyle = rgba(rgb, alpha * (.24 - ring * .04)); ctx.lineWidth = .85;
      ctx.beginPath(); ctx.ellipse(0, radius * .15, r, r * .42, 0, 0, Math.PI * 2); ctx.stroke();
    }
    var glow = ctx.createRadialGradient(0, 0, 0, 0, 0, 42);
    glow.addColorStop(0, rgba([233,247,182], alpha * .40)); glow.addColorStop(1, rgba(rgb, 0));
    ctx.fillStyle = glow; ctx.fillRect(-42, -42, 84, 84); ctx.restore();
  }
  function drawQuicken(effect, p) {
    var alpha = Math.sin(Math.PI * p) * .8, reach = (45 + p * 172) * Math.min(1.2, innerHeight / 900);
    ctx.save(); ctx.translate(effect.x, effect.y);
    for (var branch = 0; branch < 9; branch++) {
      var a = branch * Math.PI * 2 / 9 - .14;
      ctx.save(); ctx.rotate(a);
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.bezierCurveTo(14, -reach * .23, -20, -reach * .54, 0, -reach);
      ctx.strokeStyle = rgba([83, 43, 125], alpha * .50); ctx.lineWidth = 3; ctx.stroke();
      ctx.strokeStyle = rgba(colors.electro, alpha * .95); ctx.lineWidth = 1.15; ctx.stroke();
      for (var twig = 1; twig < 4; twig++) {
        var y = -reach * twig / 4, direction = twig % 2 ? -1 : 1;
        ctx.beginPath(); ctx.moveTo(0, y + 8); ctx.quadraticCurveTo(direction * 23, y - 5, direction * (18 + twig * 9), y - reach * .16);
        ctx.strokeStyle = rgba(twig % 2 ? [192,231,127] : colors.electro, alpha * .65); ctx.lineWidth = .75; ctx.stroke();
      }
      ctx.fillStyle = rgba([226,237,162], alpha * .9); ctx.beginPath(); ctx.arc(0, -reach, 1.8, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    for (var ring = 0; ring < 2; ring++) {
      ctx.strokeStyle = rgba(colors.electro, alpha * .34); ctx.lineWidth = .9; ctx.beginPath();
      ctx.ellipse(0, 8, reach * (.63 + ring * .24), reach * (.25 + ring * .08), -.12, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  }
  function draw(t, dt) {
    elapsed = t; frames++; ctx.clearRect(0, 0, W, H); ambient(t);
    reactions.forEach(function (effect) {
      if (!effect.frozen) effect.age += dt;
      var p = Math.min(1, effect.age / effect.duration);
      if (effect.type === 'electro') drawQuicken(effect, p); else drawBloom(effect, p);
    });
    reactions = reactions.filter(function (effect) { return effect.age < effect.duration; });
    // One composited shadow layer moves by only a few pixels; the city artwork does not repaint.
    if (dt) document.querySelector('.leaf-shadow').style.transform = 'translate(' + (Math.sin(t * .10) * 3).toFixed(2) + 'px,0) rotate(' + (Math.sin(t * .07) * .25).toFixed(3) + 'deg)';
  }
  function stillMode() { return snapshot || reduced.matches || document.hidden || Orbit.paused; }
  function manageMotion() {
    if (animation) { animation.stop(); animation = null; }
    if (stillMode()) {
      root.dataset.motion = 'still';
      $('motion-note').textContent = reduced.matches ? text('静态模式', 'STILL MODE') : '';
      draw(elapsed, 0);
    } else {
      root.dataset.motion = 'running'; $('motion-note').textContent = '';
      var offset = elapsed;
      animation = Orbit.loop(function (time, dt) { draw(offset + time, dt); }, { fps: 24 });
    }
  }
  function burst(type, frozen) {
    var point = centerPoint();
    reactions.push({ type: type, x: point.x, y: point.y, age: frozen || stillMode() ? 1.65 : 0, duration: 4.2, frozen: !!frozen || stillMode() });
    if (reactions.length > 3) reactions.shift();
    draw(elapsed, 0);
    var messages = {
      dendro: [ '新生 · 草木回应，枝叶舒展。', 'Awaken · the garden unfolds.' ],
      hydro: [ '绽放 · 水与草相遇，千瓣新生。', 'Bloom · water meets the living garden.' ],
      electro: [ '激化 · 雷与草交织，枝脉流光。', 'Quicken · lightning traces living veins.' ]
    };
    $('resonance-status').textContent = messages[type][zh ? 0 : 1];
  }
  function selectElement(value) {
    if (!colors[value]) return;
    element = value; root.dataset.element = value;
    document.querySelectorAll('.element').forEach(function (button) {
      var active = button.dataset.element === value; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
    });
    $('resonance-status').textContent = value === 'dendro'
      ? text('草木静候回应。轻触上方花印，唤醒庭院。', 'Dendro awaits. Touch the garden seal above.')
      : value === 'hydro' ? text('水元素已就绪。轻触花印，唤起绽放。', 'Hydro is ready. Touch the seal to bloom.')
      : text('雷元素已就绪。轻触花印，唤起激化。', 'Electro is ready. Touch the seal to quicken.');
    if (stillMode()) draw(elapsed, 0);
  }
  document.querySelectorAll('.element').forEach(function (button) { button.addEventListener('click', function () { selectElement(button.dataset.element); }); });
  $('resonance-point').addEventListener('pointermove', function (event) { pointer.active = true; pointer.x = event.clientX - box.left; pointer.y = event.clientY - box.top; });
  $('resonance-point').addEventListener('pointerleave', function () { pointer.active = false; if (stillMode()) draw(elapsed, 0); });
  $('resonance-point').addEventListener('click', function () { burst(element); });
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', manageMotion);
  Orbit.on('pause', manageMotion); Orbit.on('resume', manageMotion);
  if (reduced.addEventListener) reduced.addEventListener('change', manageMotion); else reduced.addListener(manageMotion);

  // Real action events control the ledger. A decorative event never fabricates successful work.
  function ledger(phase, message, progress) {
    root.dataset.taskPhase = phase;
    if (message) $('action-status').textContent = message;
    $('action-progress').hidden = phase !== 'running';
    $('action-progress').value = Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : 0;
    $('cancel-action').hidden = phase !== 'armed';
  }
  Orbit.on('action', function (event) {
    var phase = event.phase === 'start' || event.phase === 'progress' ? 'running' : event.phase;
    ledger(phase, event.message || (event.result && event.result.message), event.progress);
  });
  Orbit.on('confirm', function (event) { ledger(event.phase === 'cancel' ? 'canceled' : 'armed'); });
  // SDK cancels its armed action when this ordinary button receives the click.
  $('cancel-action').addEventListener('click', function () { ledger('canceled', text('已取消，未执行操作。', 'Cancelled; no operation was run.')); });
  Orbit.on('weather', function (weather) {
    $('weather-caption').textContent = weather && weather.ok
      ? (Orbit.demo ? text('示例天气 · ', 'SAMPLE · ') : '') + (weather.place || '') + (weather.stale ? text(' · 缓存', ' · cached') : '')
      : text('尚未设置城市 / 天气暂不可用', 'No city set / weather unavailable');
  });

  function applyFixture(name) {
    if (!Orbit.demo || !name) return;
    var button = document.querySelector('[data-orbit-action="tidy-files"][data-orbit-op="run"]');
    if (name === 'bloom' || name === 'quicken') { selectElement(name === 'bloom' ? 'hydro' : 'electro'); burst(element, true); }
    else if (name === 'armed') { button.classList.add('is-armed'); ledger('armed', text('将归档 6 项散落文件 · 再点一次确认（演示）', 'Would file 6 loose items · click again to confirm (demo)')); }
    else if (name === 'running') { button.classList.add('is-running'); ledger('running', text('正在归档 3 / 6 项 · 课程笔记.pdf（演示）', 'Filing 3 / 6 · Study notes.pdf (demo)'), .5); }
    else if (name === 'done') { button.classList.add('is-done'); ledger('done', text('已归档 6 项，可用“撤销归档”放回（演示）。', '6 items filed. Undo is available (demo).')); }
    else if (name === 'error') { button.classList.add('is-error'); ledger('error', text('资料目录暂不可读取，未移动文件（演示）。', 'Archive folder unavailable. No files moved (demo).')); }
    else if (name === 'partial') { ledger('partial', text('已归档 3 项；2 项保留，需检查占用状态（演示）。', '3 items filed; 2 kept. Check files in use (demo).')); }
    else if (name === 'canceled') { ledger('canceled', text('已取消，未执行归档（演示）。', 'Cancelled. No filing operation ran (demo).')); }
    else if (name === 'recovery') { ledger('recovery', text('已放回 3 项；1 项内容已改变，保留等待核查（演示）。', '3 items restored; 1 changed item kept for review (demo).')); }
    else if (name === 'empty') {
      ledger('empty', text('桌面没有待归档的散落文件（演示）。', 'No loose desktop files to archive (demo).'));
      document.querySelectorAll('[data-orbit-weather]').forEach(function (node) { node.textContent = ''; node.setAttribute('data-orbit-empty', ''); });
      $('weather-caption').textContent = text('暂无天气数据（演示）', 'No weather data (demo)');
    } else if (name === 'offline') {
      root.dataset.orbitConnection = 'offline';
      ledger('offline', text('桌面助手离线 · 便笺仍可在本机使用（演示）。', 'Helper offline · local notes remain available (demo).'));
      $('weather-caption').textContent = text('示例天气 · 当前未连接', 'SAMPLE · not connected');
    } else if (name === 'typing') {
      openNotes(true, false); note.value = text('当晚风穿过枝叶，\n记下今天尚未完成的一个念头。', 'As the evening wind crosses the leaves,\nkeep one thought for tomorrow.');
      $('note-count').textContent = text('林间灵感 · 演示', 'A garden thought · demo');
      $('note-saved').textContent = text('演示便笺 · 不保存此样例', 'Demo note · sample is not saved');
    } else { console.error('Unsupported review-state: ' + name); return; }
    root.dataset.reviewState = name;
  }
  Orbit.ready.then(function () {
    $('mode-caption').textContent = Orbit.demo ? text('预览模式 · 系统操作为演示', 'PREVIEW · SYSTEM ACTIONS SIMULATED') : text('本机桌面 · 操作连接真实系统', 'LOCAL DESKTOP · CONNECTED ACTIONS');
    resize(); applyFixture(fixture); manageMotion();
  });
  // Read-only diagnostics for repeatable QA; no controls or system access are exposed here.
  window.SumeruGarden = { metrics: function () { return { fpsCap: 24, dpr: DPR, width: canvas.width, height: canvas.height,
    activeReactions: reactions.length, maxReactions: 3, animated: !!animation, renderedFrames: frames,
    element: element, localNotes: true, reducedMotion: reduced.matches }; } };
})();
