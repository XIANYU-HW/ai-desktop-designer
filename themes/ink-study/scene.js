/* 墨痕书房 · Ink Study — scene and the glue between the functions and the painting. */
(function () {
  'use strict';
  var root = document.documentElement;
  var zh = Orbit.lang === 'zh';
  root.lang = zh ? 'zh-CN' : 'en';

  // ------------------------------------------------------------------ words
  if (!zh) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-en]'), function (el) { el.textContent = el.getAttribute('data-en'); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-en-clock]'), function (el) { el.setAttribute('data-orbit-clock', el.getAttribute('data-en-clock')); });
  }
  var DIGITS = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
  function cn(n) {
    n = Math.round(Math.abs(n));
    if (n < 10) return DIGITS[n];
    if (n < 20) return '十' + (n % 10 ? DIGITS[n % 10] : '');
    if (n < 100) return DIGITS[Math.floor(n / 10)] + '十' + (n % 10 ? DIGITS[n % 10] : '');
    return String(n).split('').map(function (d) { return DIGITS[+d]; }).join('');
  }

  var timeEl = document.getElementById('time');
  function renderTime() {
    var d = new Date();
    var hh = ('0' + d.getHours()).slice(-2), mm = ('0' + d.getMinutes()).slice(-2);
    var html = zh
      ? '<span class="tcy">' + hh + '</span>时<span class="tcy">' + mm + '</span>分'
      : '<span class="tcy">' + hh + '</span>:<span class="tcy">' + mm + '</span>';
    if (timeEl.innerHTML !== html) timeEl.innerHTML = html;
  }
  renderTime();
  setInterval(renderTime, 1000);

  Orbit.on('weather', function (w) {
    var line = document.getElementById('weather-line');
    if (!w || !w.ok) { line.textContent = ''; return; }
    var t = w.temperature == null ? '' : (zh ? (w.temperature < 0 ? '零下' : '') + cn(w.temperature) + '度' : Math.round(w.temperature) + '°');
    line.textContent = (w.condition || '') + (t ? (zh ? '　' : ' · ') + t : '');
  });

  var pendingNote = document.getElementById('pending-note');
  Orbit.on('status', function (e) {
    if (e.action !== 'tidy-files' || !e.data) return;
    var n = e.data.pending || 0;
    pendingNote.textContent = zh ? (n ? '散页' + cn(n) : '案头已净') : (n ? n + ' loose' : 'desk clear');
    looseCount = n;
  });

  var oilNote = document.getElementById('oil-note');
  Orbit.on('system', function (s) {
    if (!s || s.battery == null) { oilNote.textContent = zh ? '合上诸卷' : 'close the day'; return; }
    var tenths = Math.round(s.battery * 10);
    if (zh) oilNote.textContent = s.charging ? '添油中' : (tenths >= 10 ? '灯油满' : '灯油' + cn(tenths) + '成');
    else oilNote.textContent = s.charging ? 'oil filling' : 'oil ' + Math.round(s.battery * 100) + '%';
    lampOil = s.battery;
  });

  // ------------------------------------------------------------------ canvas
  var canvas = document.getElementById('scene');
  var ctx = canvas.getContext('2d');
  var W = 0, H = 0, DPR = 1;
  var backdrop = null, mistSprite = null;
  var looseCount = 0, lampOil = 1;

  var PALETTES = {
    dawn: { paper: [239, 225, 207], ink: [34, 30, 32], sun: [222, 120, 82], sunAlpha: 0.55, mist: [244, 234, 222] },
    day: { paper: [236, 229, 212], ink: [29, 32, 36], sun: [190, 62, 44], sunAlpha: 0.5, mist: [242, 237, 226] },
    dusk: { paper: [233, 214, 187], ink: [40, 30, 28], sun: [214, 98, 52], sunAlpha: 0.6, mist: [240, 226, 204] },
    night: { paper: [28, 30, 35], ink: [214, 210, 198], sun: [236, 230, 214], sunAlpha: 0.85, mist: [44, 47, 54], strokes: 0.35 }
  };
  function palette() { return PALETTES[root.getAttribute('data-daypart')] || PALETTES.day; }
  function rgba(c, a) { return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')'; }

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function valueNoise(seed) {
    var rand = mulberry32(seed), pts = new Float32Array(1024);
    for (var i = 0; i < pts.length; i++) pts[i] = rand();
    return function (x) {
      var i0 = Math.floor(x), f = x - i0, t = f * f * (3 - 2 * f);
      return pts[i0 & 1023] * (1 - t) + pts[(i0 + 1) & 1023] * t;
    };
  }
  function fbm(noise, x, octaves) {
    var v = 0, amp = 0.5, freq = 1, norm = 0;
    for (var o = 0; o < octaves; o++) { v += amp * noise(x * freq); norm += amp; amp *= 0.5; freq *= 2.07; }
    return v / norm;
  }

  function makeCanvas(w, h) {
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h));
    return c;
  }

  function buildMist() {
    var p = palette();
    mistSprite = makeCanvas(512, 160);
    var m = mistSprite.getContext('2d');
    var g = m.createRadialGradient(256, 80, 10, 256, 80, 256);
    g.addColorStop(0, rgba(p.mist, 0.85));
    g.addColorStop(0.55, rgba(p.mist, 0.35));
    g.addColorStop(1, rgba(p.mist, 0));
    m.setTransform(1, 0, 0, 0.3125, 0, 55);
    m.fillStyle = g;
    m.fillRect(0, -200, 512, 600);
  }

  // The mountains are painted once per size and time of day.
  function buildBackdrop() {
    var p = palette();
    backdrop = makeCanvas(W * DPR, H * DPR);
    var b = backdrop.getContext('2d');
    b.scale(DPR, DPR);
    var rand = mulberry32(20261007);

    var sky = b.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, rgba(p.paper.map(function (v) { return Math.min(255, v + 8); }), 1));
    sky.addColorStop(1, rgba(p.paper, 1));
    b.fillStyle = sky;
    b.fillRect(0, 0, W, H);

    // paper grain and fibres
    for (var i = 0; i < 2600; i++) {
      var x = rand() * W, y = rand() * H, len = 2 + rand() * 9, ang = rand() * Math.PI;
      b.strokeStyle = rgba(p.ink, 0.018 + rand() * 0.02);
      b.lineWidth = 0.6;
      b.beginPath(); b.moveTo(x, y); b.lineTo(x + Math.cos(ang) * len, y + Math.sin(ang) * len); b.stroke();
    }
    for (var s = 0; s < 14; s++) {
      var bx = rand() * W, by = rand() * H, br = 80 + rand() * 260;
      var blot = b.createRadialGradient(bx, by, 0, bx, by, br);
      blot.addColorStop(0, rgba(p.ink, 0.025)); blot.addColorStop(1, rgba(p.ink, 0));
      b.fillStyle = blot; b.fillRect(bx - br, by - br, br * 2, br * 2);
    }

    // sun or moon
    var sx = W * 0.6, sy = H * 0.2, sr = H * 0.05;
    var glow = b.createRadialGradient(sx, sy, sr * 0.8, sx, sy, sr * 2.8);
    glow.addColorStop(0, rgba(p.sun, p.sunAlpha * 0.22)); glow.addColorStop(1, rgba(p.sun, 0));
    b.fillStyle = glow; b.fillRect(sx - sr * 3, sy - sr * 3, sr * 6, sr * 6);
    b.fillStyle = rgba(p.sun, p.sunAlpha);
    b.beginPath(); b.arc(sx, sy, sr, 0, Math.PI * 2); b.fill();

    // five ranges of mountains, far to near: pale and soft far away, dark ridges close by
    var layers = [
      { base: 0.47, amp: 0.21, freq: 1.15, alpha: 0.085, seed: 11, foot: 0.2, blur: 2.4 },
      { base: 0.54, amp: 0.3, freq: 1.6, alpha: 0.14, seed: 23, foot: 0.19, blur: 1.4 },
      { base: 0.62, amp: 0.26, freq: 2.2, alpha: 0.22, seed: 37, foot: 0.16, blur: 0.6 },
      { base: 0.7, amp: 0.19, freq: 2.9, alpha: 0.34, seed: 41, foot: 0.13, blur: 0 },
      { base: 0.78, amp: 0.1, freq: 3.7, alpha: 0.48, seed: 53, foot: 0.09, blur: 0 }
    ];
    var canBlur = typeof b.filter === 'string';
    layers.forEach(function (layer, index) {
      var noise = valueNoise(layer.seed);
      var ridge = [];
      for (var x = -8; x <= W + 8; x += 3) {
        var u = x / W * layer.freq + layer.seed;
        // ridged noise gives peaks, plain noise gives rolling flanks, a slow envelope groups them
        var ridged = 0, amp = 0.5, freq = 1, norm = 0;
        for (var o = 0; o < 4; o++) {
          ridged += amp * Math.pow(1 - Math.abs(2 * noise(u * freq * 1.3) - 1), 2);
          norm += amp; amp *= 0.5; freq *= 2.1;
        }
        ridged /= norm;
        var envelope = 0.3 + 0.7 * Math.pow(noise(u * 0.33 + 50), 1.3);
        var h = (0.62 * ridged + 0.38 * fbm(noise, u + 9, 5)) * envelope;
        var calm = 1 - 0.5 * Math.max(0, (x / W - 0.62) / 0.38); // keep the colophon side low
        ridge.push([x, H * layer.base - H * layer.amp * Math.pow(h, 1.25) * 2.1 * calm]);
      }
      var top = Math.min.apply(null, ridge.map(function (pt) { return pt[1]; }));
      var bottom = H * (layer.base + layer.foot);
      var fill = b.createLinearGradient(0, top, 0, bottom);
      fill.addColorStop(0, rgba(p.ink, layer.alpha));
      fill.addColorStop(0.5, rgba(p.ink, layer.alpha * 0.5));
      fill.addColorStop(1, rgba(p.ink, 0));
      b.save();
      if (canBlur && layer.blur) b.filter = 'blur(' + layer.blur + 'px)';
      b.fillStyle = fill;
      b.beginPath();
      b.moveTo(ridge[0][0], bottom);
      ridge.forEach(function (pt) { b.lineTo(pt[0], pt[1]); });
      b.lineTo(ridge[ridge.length - 1][0], bottom);
      b.closePath();
      b.fill();
      b.restore();

      // texture strokes (皴) that follow the slope, gathered under the peaks
      var r2 = mulberry32(layer.seed * 97);
      var strokes = 40 + index * 30;
      for (var k = 0; k < strokes; k++) {
        var at = Math.floor(r2() * (ridge.length - 2)) + 1;
        var pt = ridge[at];
        var slope = (ridge[at + 1][1] - ridge[at - 1][1]) / 6;
        if (pt[1] > H * layer.base - H * layer.amp * 0.15 && r2() < 0.7) continue; // fewer strokes in the valleys
        var depth = Math.pow(r2(), 2) * H * (0.03 + index * 0.012);
        var len2 = H * (0.006 + r2() * (0.011 + index * 0.004));
        var dir = slope > 0 ? 1 : -1;
        b.strokeStyle = rgba(p.ink, layer.alpha * (0.25 + r2() * 0.45) * (p.strokes || 1));
        b.lineWidth = 0.5 + r2() * (0.5 + index * 0.3);
        b.lineCap = 'round';
        b.beginPath();
        b.moveTo(pt[0], pt[1] + depth);
        b.quadraticCurveTo(pt[0] + dir * len2 * 0.25, pt[1] + depth + len2 * 0.5, pt[0] + dir * len2 * (0.35 + r2() * 0.3), pt[1] + depth + len2);
        b.stroke();
      }
      // the ridge line, drawn with a dry brush of changing weight
      if (!layer.blur || layer.blur < 1) {
        b.lineCap = 'butt';
        for (var seg = 1; seg < ridge.length; seg++) {
          var a0 = ridge[seg - 1], a1 = ridge[seg];
          b.strokeStyle = rgba(p.ink, Math.min(0.8, layer.alpha * (1.1 + 0.5 * noise(seg * 0.05 + 3))) * (p.strokes ? 0.55 : 1));
          b.lineWidth = (0.6 + index * 0.3) * (0.5 + noise(seg * 0.07 + 7));
          b.beginPath(); b.moveTo(a0[0], a0[1]); b.lineTo(a1[0], a1[1]); b.stroke();
        }
      }
    });

    // the water: a few faint ripples
    for (var w = 0; w < 46; w++) {
      var wy = H * (0.86 + rand() * 0.12), wx = rand() * W, wl = 16 + rand() * 90;
      b.strokeStyle = rgba(p.ink, 0.03 + rand() * 0.03);
      b.lineWidth = 0.8;
      b.beginPath(); b.moveTo(wx, wy); b.lineTo(wx + wl, wy); b.stroke();
    }
  }

  // ------------------------------------------------------------------ moving things
  var mists = [];
  var birds = [];
  var blooms = [];
  var slips = [];
  var embers = [];
  var drops = [];
  var dim = 0, dimTarget = 0, lampArmed = false, flash = 0;

  function seedMoving() {
    var rand = mulberry32(7);
    mists = [];
    for (var i = 0; i < 7; i++) {
      mists.push({ y: 0.5 + rand() * 0.38, w: 0.5 + rand() * 0.7, h: 0.08 + rand() * 0.09, speed: 4 + rand() * 9, off: rand() * 4000, a: 0.45 + rand() * 0.4 });
    }
    birds = [];
    for (var j = 0; j < 3; j++) birds.push({ off: j * 0.035, dy: (rand() - 0.5) * 0.03, flap: rand() * 6 });
    drops = [];
    var rain = mulberry32(99);
    for (var k = 0; k < 160; k++) drops.push({ x: rain(), y: rain(), v: 0.6 + rain() * 0.6, l: 0.012 + rain() * 0.02 });
  }

  function centerOf(el) {
    var r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height * 0.42 };
  }
  var tidyEl = document.getElementById('slip-tidy');
  var lampEl = document.getElementById('slip-lamp');

  function spawnSlip(direction) {
    var target = centerOf(tidyEl);
    var from = { x: W * (0.06 + Math.random() * 0.3), y: H * (0.12 + Math.random() * 0.6) };
    slips.push({
      a: direction === 'in' ? from : target,
      b: direction === 'in' ? target : from,
      c: { x: (from.x + target.x) / 2 + (Math.random() - 0.5) * W * 0.2, y: Math.min(from.y, target.y) - H * (0.1 + Math.random() * 0.15) },
      t: 0, dur: 1.2 + Math.random() * 0.5, spin: (Math.random() - 0.5) * 6, dir: direction
    });
  }
  function bloom(x, y, color, size) {
    blooms.push({ x: x, y: y, r: 2, max: size || H * 0.06, life: 0, color: color });
  }

  Orbit.on('action', function (e) {
    if (e.action === 'tidy-files') {
      if (e.phase === 'progress' && e.status === 'moved') spawnSlip('in');
      if (e.phase === 'progress' && e.status === 'restored') spawnSlip('out');
      if (e.phase === 'done' && e.op === 'run') { var c = centerOf(tidyEl); bloom(c.x, c.y, palette().ink, H * 0.09); }
      if (e.phase === 'error') { var c2 = centerOf(tidyEl); bloom(c2.x, c2.y, [178, 58, 42], H * 0.05); }
    }
    if (e.action === 'quit-apps') {
      if (e.phase === 'start' && e.op === 'run') { dimTarget = 1; lampArmed = false; }
      if (e.phase === 'progress' && (e.status === 'closed' || e.status === 'hidden')) {
        var l = centerOf(lampEl);
        for (var i = 0; i < 6; i++) embers.push({ x: l.x + (Math.random() - 0.5) * 18, y: l.y - H * 0.06, vx: (Math.random() - 0.5) * 14, vy: -20 - Math.random() * 30, life: 0 });
      }
      if (e.phase === 'done' && e.op === 'run') setTimeout(function () { dimTarget = 0; }, 20000);
      if (e.op === 'reopen' && e.phase === 'start') { dimTarget = 0; flash = 1; }
    }
  });
  Orbit.on('confirm', function (e) { lampArmed = e.action === 'quit-apps' && e.phase === 'armed'; });
  Orbit.on('daypart', function () { buildBackdrop(); buildMist(); });

  function quad(a, c, b, t) {
    var u = 1 - t;
    return { x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y };
  }

  function draw(t, dt) {
    var p = palette();
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.drawImage(backdrop, 0, 0, W, H);

    // mist bands drifting slowly to the right
    var mistBoost = 1 + dim * 0.8 + (root.getAttribute('data-weather') === 'fog' ? 0.8 : 0);
    mists.forEach(function (m) {
      var bw = W * m.w, bh = H * m.h;
      var x = ((t * m.speed + m.off) % (W + bw)) - bw;
      ctx.globalAlpha = Math.min(1, m.a * mistBoost);
      ctx.drawImage(mistSprite, x, H * m.y - bh / 2, bw, bh);
    });
    ctx.globalAlpha = 1;

    // a lone boat with a fisherman, crossing over many minutes
    var bxp = W * (0.33 + 0.16 * Math.sin(t / 140)), byp = H * 0.865 + Math.sin(t * 0.7) * 1.2;
    ctx.save();
    ctx.translate(bxp, byp);
    var s = H / 720;
    ctx.fillStyle = rgba(p.ink, 0.78);
    ctx.beginPath();
    ctx.moveTo(-26 * s, 0); ctx.quadraticCurveTo(0, 9 * s, 30 * s, -2 * s); ctx.lineTo(24 * s, 2 * s); ctx.quadraticCurveTo(0, 6 * s, -22 * s, 2 * s);
    ctx.fill();
    ctx.beginPath(); ctx.ellipse(-2 * s, -7 * s, 3.4 * s, 6 * s, 0, 0, Math.PI * 2); ctx.fill(); // the fisherman
    ctx.beginPath(); ctx.moveTo(-5 * s, -15 * s); ctx.lineTo(1 * s, -13 * s); ctx.lineTo(-2 * s, -10 * s); ctx.fill(); // hat
    ctx.strokeStyle = rgba(p.ink, 0.55); ctx.lineWidth = Math.max(0.6, 0.9 * s);
    ctx.beginPath(); ctx.moveTo(0, -8 * s); ctx.quadraticCurveTo(26 * s, -30 * s, 54 * s, -20 * s); ctx.stroke(); // rod
    ctx.beginPath(); ctx.moveTo(54 * s, -20 * s); ctx.lineTo(56 * s, 4 * s); ctx.stroke(); // line
    ctx.globalAlpha = 0.18;
    ctx.scale(1, -0.5);
    ctx.fillStyle = rgba(p.ink, 0.6);
    ctx.beginPath(); ctx.moveTo(-24 * s, -2 * s); ctx.quadraticCurveTo(0, 9 * s, 28 * s, -2 * s); ctx.fill();
    ctx.restore();
    ctx.globalAlpha = 1;

    // birds pass every couple of minutes
    var cycle = (t % 150) / 150;
    if (cycle < 0.3) {
      var progress = cycle / 0.3;
      birds.forEach(function (bird) {
        var x = W * (1.05 - progress * 1.2 + bird.off), y = H * (0.28 + bird.dy) + Math.sin(progress * 6 + bird.flap) * H * 0.01;
        var wing = Math.sin(t * 5 + bird.flap) * 3 * s + 4 * s;
        ctx.strokeStyle = rgba(p.ink, 0.6); ctx.lineWidth = Math.max(0.7, 1.1 * s);
        ctx.beginPath(); ctx.moveTo(x - 7 * s, y - wing); ctx.quadraticCurveTo(x - 3 * s, y - 1 * s, x, y); ctx.quadraticCurveTo(x + 3 * s, y - 1 * s, x + 7 * s, y - wing); ctx.stroke();
      });
    }

    // weather: ink rain or paper snow
    var weather = root.getAttribute('data-weather');
    if (weather === 'rain' || weather === 'drizzle' || weather === 'storm' || weather === 'snow') {
      var snow = weather === 'snow';
      ctx.strokeStyle = rgba(p.ink, weather === 'drizzle' ? 0.12 : 0.2);
      ctx.fillStyle = rgba(p.mist, 0.9);
      ctx.lineWidth = 0.8;
      var count = weather === 'drizzle' ? 70 : drops.length;
      for (var i = 0; i < count; i++) {
        var d = drops[i];
        var y = ((d.y + t * d.v * (snow ? 0.05 : 0.6)) % 1) * H;
        var x = ((d.x + (snow ? Math.sin(t * 0.5 + i) * 0.01 : y / H * 0.06)) % 1) * W;
        if (snow) { ctx.beginPath(); ctx.arc(x, y, 1.2 + d.v, 0, Math.PI * 2); ctx.fill(); }
        else { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + H * d.l * 0.25, y + H * d.l); ctx.stroke(); }
      }
    }

    // paper slips flying between the desktop and the scroll
    slips = slips.filter(function (slip) {
      slip.t += dt / slip.dur;
      if (slip.t >= 1) {
        if (slip.dir === 'in') bloom(slip.b.x, slip.b.y, p.ink, H * 0.03);
        return false;
      }
      var e = slip.t < 0.5 ? 2 * slip.t * slip.t : 1 - Math.pow(-2 * slip.t + 2, 2) / 2;
      var pos = quad(slip.a, slip.c, slip.b, e);
      var scale = H / 1000 * (slip.dir === 'in' ? 1 - e * 0.55 : 0.45 + e * 0.55);
      ctx.save();
      ctx.translate(pos.x, pos.y);
      ctx.rotate(slip.spin * e);
      ctx.globalAlpha = slip.dir === 'in' ? Math.min(1, (1 - slip.t) * 3) : Math.min(1, (1 - slip.t) * 2.5);
      ctx.fillStyle = rgba(p.paper.map(function (v) { return Math.min(255, v + 12); }), 1);
      ctx.strokeStyle = rgba(p.ink, 0.5);
      ctx.lineWidth = 0.8;
      ctx.fillRect(-9 * scale, -13 * scale, 18 * scale, 26 * scale);
      ctx.strokeRect(-9 * scale, -13 * scale, 18 * scale, 26 * scale);
      ctx.beginPath();
      for (var ln = 0; ln < 3; ln++) { ctx.moveTo((-4 + ln * 4) * scale, -8 * scale); ctx.lineTo((-4 + ln * 4) * scale, 8 * scale); }
      ctx.stroke();
      ctx.restore();
      return true;
    });
    ctx.globalAlpha = 1;

    // ink blooms
    blooms = blooms.filter(function (bl) {
      bl.life += dt;
      var k = Math.min(1, bl.life / 1.6);
      bl.r = bl.max * (1 - Math.pow(1 - k, 3));
      ctx.strokeStyle = rgba(bl.color, 0.35 * (1 - k));
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(bl.x, bl.y, bl.r, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(bl.x, bl.y, bl.r * 0.62, 0, Math.PI * 2); ctx.stroke();
      return k < 1;
    });

    // the lamp: glows warm while asking for confirmation, embers rise as apps close
    if (lampArmed) {
      var l = centerOf(lampEl);
      var pulse = 0.55 + 0.25 * Math.sin(t * 4);
      var lg = ctx.createRadialGradient(l.x, l.y, 0, l.x, l.y, H * 0.22);
      lg.addColorStop(0, 'rgba(226,167,74,' + (0.35 * pulse) + ')'); lg.addColorStop(1, 'rgba(226,167,74,0)');
      ctx.fillStyle = lg; ctx.fillRect(l.x - H * 0.22, l.y - H * 0.22, H * 0.44, H * 0.44);
    }
    embers = embers.filter(function (em) {
      em.life += dt; em.x += em.vx * dt; em.y += em.vy * dt; em.vy -= 6 * dt;
      ctx.fillStyle = 'rgba(226,167,74,' + Math.max(0, 0.8 - em.life * 0.6) + ')';
      ctx.beginPath(); ctx.arc(em.x, em.y, 1.6, 0, Math.PI * 2); ctx.fill();
      return em.life < 1.4;
    });

    // ink deepens after the lamp goes out, and lifts again later
    dim += (dimTarget - dim) * Math.min(1, dt * (dimTarget > dim ? 0.8 : 0.15));
    if (dim > 0.01) { ctx.fillStyle = rgba(p.ink, 0.22 * dim); ctx.fillRect(0, 0, W, H); }
    if (flash > 0.01) { ctx.fillStyle = 'rgba(255,236,200,' + (0.18 * flash) + ')'; ctx.fillRect(0, 0, W, H); flash *= Math.pow(0.2, dt); }
  }

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    // a wallpaper host can report a zero-sized window for a moment while it starts
    W = window.innerWidth || screen.width || 1280; H = window.innerHeight || screen.height || 720;
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    buildBackdrop();
    buildMist();
  }

  var resizeTimer = 0;
  window.addEventListener('resize', function () { clearTimeout(resizeTimer); resizeTimer = setTimeout(resize, 150); });
  resize();
  seedMoving();
  Orbit.loop(draw, { fps: 24 });
})();
