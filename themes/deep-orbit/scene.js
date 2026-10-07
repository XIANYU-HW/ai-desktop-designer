/* Deep Orbit · 深空轨道 — planet, satellites (open apps), debris (loose files), captures and silent running. */
(function () {
  'use strict';
  var root = document.documentElement;
  var zh = Orbit.lang === 'zh';
  root.lang = zh ? 'zh-CN' : 'en';
  Array.prototype.forEach.call(document.querySelectorAll('[data-zh]'), function (el) {
    el.textContent = zh ? el.getAttribute('data-zh') : '';
  });

  var canvas = document.getElementById('scene');
  var ctx = canvas.getContext('2d');
  var W = 0, H = 0, DPR = 1;
  var stars = [], debris = [], captured = [], satellites = [], flights = [], sparks = [];
  var planet = { x: 0, y: 0, r: 0 };
  var rings = [];
  var tilt = -0.1;
  var silent = 0, silentTarget = 0, starSpeed = 1;
  var archiveGlow = 0;
  var backdrop = null;

  function rand(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function layout() {
    planet.r = H * 0.5;
    planet.x = W * 0.66;
    planet.y = H * 1.12;
    // seen from well above the orbital plane, so the far half of each orbit arcs over the planet
    rings = [
      { rx: planet.r * 1.62, ry: planet.r * 1.0, speed: 0.06, alpha: 0.22 },
      { rx: planet.r * 1.95, ry: planet.r * 1.2, speed: 0.042, alpha: 0.18 },
      { rx: planet.r * 2.3, ry: planet.r * 1.42, speed: 0.03, alpha: 0.2, archive: true }
    ];
  }

  function onRing(ring, angle) {
    var ex = Math.cos(angle) * ring.rx, ey = Math.sin(angle) * ring.ry;
    return {
      x: planet.x + ex * Math.cos(tilt) - ey * Math.sin(tilt),
      y: planet.y + ex * Math.sin(tilt) + ey * Math.cos(tilt),
      front: Math.sin(angle) > 0
    };
  }

  function buildStars() {
    var r = rand(42);
    stars = [];
    var layers = [{ n: 520, size: 0.6, speed: 0.0015 }, { n: 220, size: 1.0, speed: 0.003 }, { n: 70, size: 1.5, speed: 0.006 }];
    layers.forEach(function (layer, depth) {
      for (var i = 0; i < layer.n; i++) {
        stars.push({ x: r(), y: r(), s: layer.size * (0.6 + r() * 0.8), speed: layer.speed, phase: r() * 6.28, depth: depth, warm: r() < 0.12 });
      }
    });
  }

  function buildBackdrop() {
    backdrop = document.createElement('canvas');
    backdrop.width = Math.round(W * DPR); backdrop.height = Math.round(H * DPR);
    var b = backdrop.getContext('2d');
    b.scale(DPR, DPR);
    var sky = b.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, '#04060b'); sky.addColorStop(0.6, '#070b16'); sky.addColorStop(1, '#0b1224');
    b.fillStyle = sky; b.fillRect(0, 0, W, H);
    // a faint band of galaxy dust across the sky
    var r = rand(7);
    for (var i = 0; i < 260; i++) {
      var t = r(), x = t * W, y = H * (0.18 + 0.32 * t) + (r() - 0.5) * H * 0.22, size = 30 + r() * 120;
      var g = b.createRadialGradient(x, y, 0, x, y, size);
      var hue = r() < 0.5 ? '120,150,255' : '180,120,255';
      g.addColorStop(0, 'rgba(' + hue + ',' + (0.012 + r() * 0.018) + ')'); g.addColorStop(1, 'rgba(' + hue + ',0)');
      b.fillStyle = g; b.fillRect(x - size, y - size, size * 2, size * 2);
    }
  }

  function syncSatellites(count) {
    count = Math.max(0, Math.min(24, count | 0));
    var r = rand(satellites.length + 11);
    satellites = satellites.filter(function (s) { return !(s.leaving && s.light < 0.03); });
    var active = satellites.filter(function (s) { return !s.leaving; });
    while (active.length < count) {
      var ring = rings[active.length % 2];
      var sat = { ring: ring, angle: Math.PI * (1.1 + r() * 0.8), speed: ring.speed * (0.8 + r() * 0.5), light: 0, target: 1, leaving: false };
      satellites.push(sat);
      active.push(sat);
    }
    active.slice(count).forEach(function (s) { s.leaving = true; s.target = 0; });
  }

  function syncDebris(count) {
    count = Math.max(0, Math.min(160, count | 0));
    var r = rand(debris.length + 99);
    while (debris.length < count) {
      debris.push({ angle: Math.PI * (1.05 + r() * 0.9), dist: 2.45 + r() * 0.75, speed: 0.006 + r() * 0.012, wobble: r() * 6.28, size: 1.3 + r() * 1.7, spin: r() * 6.28 });
    }
    while (debris.length > count) debris.pop();
  }

  function debrisPos(d, t) {
    var ring = { rx: planet.r * d.dist, ry: planet.r * d.dist * 0.6 };
    var p = onRing(ring, d.angle);
    p.y += Math.sin(t * 0.3 + d.wobble) * H * 0.006;
    return p;
  }

  // ------------------------------------------------------------------ data → scene
  Orbit.on('status', function (e) {
    if (e.action === 'tidy-files' && e.data && typeof e.data.pending === 'number') syncDebris(e.data.pending);
    if (e.action === 'quit-apps' && e.data && typeof e.data.open === 'number' && silentTarget === 0) syncSatellites(e.data.open);
  });

  var archiveRingIndex = 2;
  Orbit.on('action', function (e) {
    if (e.action === 'tidy-files' && e.phase === 'progress') {
      if (e.status === 'moved' && debris.length) {
        var d = debris.splice(Math.floor(Math.random() * debris.length), 1)[0];
        var from = debrisPos(d, 0);
        flights.push({ from: from, angle: Math.random() * 6.28, t: 0, dur: 1.4, kind: 'capture' });
      }
      if (e.status === 'restored') {
        var leaving = captured.shift();
        var start = leaving ? onRing(rings[archiveRingIndex], leaving.angle) : { x: planet.x, y: planet.y - planet.r };
        flights.push({ from: start, to: { x: W * (0.15 + Math.random() * 0.5), y: H * (0.2 + Math.random() * 0.5) }, t: 0, dur: 1.6, kind: 'release' });
      }
    }
    if (e.action === 'tidy-files' && e.phase === 'done') archiveGlow = 1;
    if (e.action === 'quit-apps') {
      if (e.phase === 'start' && e.op === 'run') { silentTarget = 1; root.classList.add('silent'); }
      if (e.phase === 'progress' && (e.status === 'closed' || e.status === 'hidden')) {
        var lit = satellites.filter(function (s) { return !s.leaving && s.target > 0; });
        if (lit.length) {
          var sat = lit[Math.floor(Math.random() * lit.length)];
          sat.target = 0;
          var p = onRing(sat.ring, sat.angle);
          for (var i = 0; i < 10; i++) sparks.push({ x: p.x, y: p.y, vx: (Math.random() - 0.5) * 40, vy: (Math.random() - 0.5) * 40, life: 0 });
        }
      }
      if (e.phase === 'done' && e.op === 'run') setTimeout(function () { silentTarget = 0.35; }, 6000);
      if (e.op === 'reopen' && e.phase === 'start') { silentTarget = 0; root.classList.remove('silent'); satellites.forEach(function (s) { s.target = 1; }); }
    }
  });

  // ------------------------------------------------------------------ drawing
  var planetLayer = null, planetBox = null;
  function buildPlanet() {
    var p = planet, pad = p.r * 0.2;
    planetBox = { x: p.x - p.r - pad, y: p.y - p.r - pad, size: (p.r + pad) * 2 };
    planetLayer = document.createElement('canvas');
    planetLayer.width = planetLayer.height = Math.round(planetBox.size * DPR);
    var b = planetLayer.getContext('2d');
    b.scale(DPR, DPR);
    b.translate(-planetBox.x, -planetBox.y);
    var atmosphere = b.createRadialGradient(p.x, p.y, p.r * 0.96, p.x, p.y, p.r * 1.18);
    atmosphere.addColorStop(0, 'rgba(99,200,255,0.22)'); atmosphere.addColorStop(1, 'rgba(99,200,255,0)');
    b.fillStyle = atmosphere;
    b.beginPath(); b.arc(p.x, p.y, p.r * 1.18, 0, Math.PI * 2); b.fill();
    var body = b.createRadialGradient(p.x - p.r * 0.35, p.y - p.r * 0.55, p.r * 0.1, p.x, p.y, p.r);
    body.addColorStop(0, '#1b3558'); body.addColorStop(0.55, '#0c1a30'); body.addColorStop(1, '#03070f');
    b.fillStyle = body;
    b.beginPath(); b.arc(p.x, p.y, p.r, 0, Math.PI * 2); b.fill();
    b.strokeStyle = 'rgba(120,220,255,0.55)';
    b.lineWidth = 1.5;
    b.beginPath(); b.arc(p.x, p.y, p.r, Math.PI * 1.08, Math.PI * 1.62); b.stroke();
  }

  function drawPlanet(t) {
    var p = planet;
    ctx.drawImage(planetLayer, planetBox.x, planetBox.y, planetBox.size, planetBox.size);

    // cloud bands and city lights are the only parts that move
    ctx.save();
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.clip();
    for (var i = 0; i < 9; i++) {
      var y = p.y - p.r + p.r * (0.08 + i * 0.07);
      ctx.strokeStyle = 'rgba(160,200,255,' + (0.035 + (i % 3) * 0.012) + ')';
      ctx.lineWidth = p.r * (0.01 + (i % 4) * 0.006);
      ctx.beginPath();
      for (var x = p.x - p.r; x <= p.x + p.r; x += 12) {
        var yy = y + Math.sin(x * 0.006 + t * 0.02 + i) * p.r * 0.012;
        if (x === p.x - p.r) ctx.moveTo(x, yy); else ctx.lineTo(x, yy);
      }
      ctx.stroke();
    }
    // city lights on the night side
    var r = rand(5);
    for (var c = 0; c < 140; c++) {
      var a = Math.PI * (1.05 + r() * 0.5), dist = p.r * (0.55 + r() * 0.42);
      var cx = p.x + Math.cos(a) * dist, cy = p.y + Math.sin(a) * dist;
      var flicker = 0.35 + 0.25 * Math.sin(t * 0.8 + c);
      ctx.fillStyle = 'rgba(255,190,110,' + (flicker * (1 - silent * 0.7) * 0.5) + ')';
      ctx.fillRect(cx, cy, 1.4, 1.4);
    }
    ctx.restore();
  }

  function drawRing(ring, front) {
    ctx.save();
    ctx.translate(planet.x, planet.y);
    ctx.rotate(tilt);
    ctx.strokeStyle = ring.archive
      ? 'rgba(99,230,255,' + (ring.alpha + archiveGlow * 0.4) + ')'
      : 'rgba(150,190,255,' + ring.alpha + ')';
    ctx.lineWidth = ring.archive ? 1 + archiveGlow * 1.5 : 1;
    if (ring.archive) ctx.setLineDash([2, 6]);
    ctx.beginPath();
    ctx.ellipse(0, 0, ring.rx, ring.ry, 0, front ? 0 : Math.PI, front ? Math.PI : Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  // Glows are pre-rendered sprites: soft, cheap to draw, and identical every frame.
  var glowCache = {};
  function glowSprite(color) {
    if (glowCache[color]) return glowCache[color];
    var c = document.createElement('canvas');
    c.width = c.height = 64;
    var g = c.getContext('2d');
    var grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(' + color + ',1)');
    grad.addColorStop(0.22, 'rgba(' + color + ',0.38)');
    grad.addColorStop(1, 'rgba(' + color + ',0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
    return (glowCache[color] = c);
  }

  function glowDot(x, y, radius, color, alpha) {
    var size = radius * 8;
    ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
    ctx.drawImage(glowSprite(color), x - size / 2, y - size / 2, size, size);
    ctx.globalAlpha = 1;
    ctx.fillStyle = 'rgba(' + color + ',' + Math.min(1, alpha * 1.4) + ')';
    ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill();
  }

  function drawOrbiters(t, dt, front) {
    satellites.forEach(function (s) {
      if (front) {
        s.angle += s.speed * dt * (1 - silent * 0.6);
        s.light += (s.target - s.light) * Math.min(1, dt * 1.5);
      }
      var p = onRing(s.ring, s.angle);
      if (p.front !== front) return;
      ctx.fillStyle = 'rgba(200,220,255,0.55)';
      ctx.fillRect(p.x - 1.5, p.y - 1.5, 3, 3);
      if (s.light > 0.02) glowDot(p.x, p.y, 2.4, '140,240,255', 0.9 * s.light * (0.75 + 0.25 * Math.sin(t * 3 + s.angle * 5)));
    });
    captured.forEach(function (c) {
      if (front) c.angle += rings[archiveRingIndex].speed * dt;
      var p = onRing(rings[archiveRingIndex], c.angle);
      if (p.front !== front) return;
      glowDot(p.x, p.y, 1.4, '99,230,255', 0.75);
    });
  }

  function draw(t, dt) {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.drawImage(backdrop, 0, 0, W, H);

    silent += (silentTarget - silent) * Math.min(1, dt * 0.6);
    starSpeed = 1 - silent * 0.8;
    archiveGlow *= Math.pow(0.35, dt);

    // stars with parallax drift
    stars.forEach(function (s) {
      s.x -= s.speed * dt * starSpeed * 0.2;
      if (s.x < 0) s.x += 1;
      var twinkle = 0.55 + 0.45 * Math.sin(t * (0.6 + s.depth * 0.4) + s.phase);
      ctx.fillStyle = s.warm ? 'rgba(255,214,170,' + (twinkle * 0.8) + ')' : 'rgba(210,228,255,' + (twinkle * (0.45 + s.depth * 0.2)) + ')';
      ctx.fillRect(s.x * W, s.y * H, s.s, s.s);
    });

    rings.forEach(function (ring) { drawRing(ring, false); });
    drawOrbiters(t, dt, false);

    // debris field behind and around the planet
    debris.forEach(function (d) {
      d.angle += d.speed * dt;
      var p = debrisPos(d, t);
      // a tumbling fragment: a small irregular quad with a glint
      var a = d.spin + t * 0.4, sz = d.size * 1.6;
      ctx.fillStyle = 'rgba(190,200,220,' + (p.front ? 0.85 : 0.65) + ')';
      ctx.beginPath();
      ctx.moveTo(p.x + Math.cos(a) * sz, p.y + Math.sin(a) * sz);
      ctx.lineTo(p.x + Math.cos(a + 2.1) * sz * 0.7, p.y + Math.sin(a + 2.1) * sz * 0.7);
      ctx.lineTo(p.x + Math.cos(a + 3.4) * sz, p.y + Math.sin(a + 3.4) * sz);
      ctx.lineTo(p.x + Math.cos(a + 4.8) * sz * 0.6, p.y + Math.sin(a + 4.8) * sz * 0.6);
      ctx.closePath(); ctx.fill();
      if (Math.sin(t * 1.3 + d.wobble) > 0.92) glowDot(p.x, p.y, 1, '255,255,255', 0.6);
    });

    drawPlanet(t);
    rings.forEach(function (ring) { drawRing(ring, true); });
    drawOrbiters(t, dt, true);

    // captures and releases in flight
    flights = flights.filter(function (f) {
      f.t = Math.min(1, f.t + dt / f.dur);
      var to = f.kind === 'capture' ? onRing(rings[archiveRingIndex], f.angle) : f.to;
      function at(k) {
        var e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        return { x: f.from.x + (to.x - f.from.x) * e, y: f.from.y + (to.y - f.from.y) * e - Math.sin(e * Math.PI) * H * 0.05 };
      }
      var head = at(f.t), tail = at(Math.max(0, f.t - 0.14));
      var color = f.kind === 'capture' ? '99,230,255' : '255,181,71';
      var trail = ctx.createLinearGradient(tail.x, tail.y, head.x, head.y);
      trail.addColorStop(0, 'rgba(' + color + ',0)'); trail.addColorStop(1, 'rgba(' + color + ',0.6)');
      ctx.strokeStyle = trail;
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(tail.x, tail.y); ctx.lineTo(head.x, head.y); ctx.stroke();
      glowDot(head.x, head.y, 1.8, color, 0.9);
      if (f.t >= 1) {
        if (f.kind === 'capture') captured.push({ angle: f.angle });
        if (captured.length > 200) captured.shift();
        return false;
      }
      return true;
    });

    sparks = sparks.filter(function (s) {
      s.life += dt; s.x += s.vx * dt; s.y += s.vy * dt;
      ctx.fillStyle = 'rgba(255,181,71,' + Math.max(0, 1 - s.life * 1.4) + ')';
      ctx.fillRect(s.x, s.y, 1.5, 1.5);
      return s.life < 0.8;
    });

    if (silent > 0.01) {
      ctx.fillStyle = 'rgba(2,4,8,' + (silent * 0.35) + ')';
      ctx.fillRect(0, 0, W, H);
    }
  }

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth || screen.width || 1280;
    H = window.innerHeight || screen.height || 720;
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    layout();
    buildBackdrop();
    buildPlanet();
  }

  var timer = 0;
  window.addEventListener('resize', function () { clearTimeout(timer); timer = setTimeout(resize, 150); });
  resize();
  buildStars();
  syncSatellites(5);
  syncDebris(12);
  Orbit.loop(draw, { fps: 60 });   // continuous motion: 60 fps on pre-rendered layers
})();
