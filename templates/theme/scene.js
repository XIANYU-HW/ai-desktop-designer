/* The scene and the glue between functions and the world. */
(function () {
  'use strict';
  var zh = Orbit.lang === 'zh';
  document.documentElement.lang = zh ? 'zh-CN' : 'en';
  if (!zh) {   // markup is written in Chinese; swap in English where data-en is given
    document.querySelectorAll('[data-en]').forEach(function (el) { el.textContent = el.getAttribute('data-en'); });
    document.querySelectorAll('[data-en-clock]').forEach(function (el) { el.setAttribute('data-orbit-clock', el.getAttribute('data-en-clock')); });
  }

  var canvas = document.getElementById('scene');
  var ctx = canvas.getContext('2d');
  var W = 0, H = 0, DPR = 1;
  var backdrop = null;      // static layers painted once
  var effects = [];         // short-lived things spawned by events

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth || screen.width || 1280;    // hosts can report 0 while starting
    H = window.innerHeight || screen.height || 720;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    paintBackdrop();
  }

  function paintBackdrop() {
    backdrop = document.createElement('canvas');
    backdrop.width = canvas.width; backdrop.height = canvas.height;
    var b = backdrop.getContext('2d');
    b.scale(DPR, DPR);
    var g = b.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#16181d'); g.addColorStop(1, '#0c0d10');
    b.fillStyle = g; b.fillRect(0, 0, W, H);
    // paint the world's static layers here
  }

  // Real events become the world's motion.
  Orbit.on('action', function (e) {
    if (e.action === 'tidy-files' && e.phase === 'progress' && e.status === 'moved') {
      effects.push({ x: Math.random() * W * 0.4, y: Math.random() * H * 0.7, life: 0 });   // one per filed item
    }
    if (e.action === 'quit-apps' && e.phase === 'start' && e.op === 'run') { /* begin winding down */ }
  });
  Orbit.on('status', function (e) { /* e.g. keep as many objects as e.data.pending */ });
  Orbit.on('daypart', paintBackdrop);

  function draw(t, dt) {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.drawImage(backdrop, 0, 0, W, H);
    // slow ambient motion here
    effects = effects.filter(function (fx) {
      fx.life += dt;
      ctx.fillStyle = 'rgba(217,165,91,' + Math.max(0, 1 - fx.life) + ')';
      ctx.beginPath(); ctx.arc(fx.x, fx.y, 3 + fx.life * 20, 0, Math.PI * 2); ctx.fill();
      return fx.life < 1;
    });
  }

  window.addEventListener('resize', resize);
  resize();
  Orbit.loop(draw, { fps: 60 });   // pauses when the desktop is covered or hidden; 60 fps for continuous motion
})();
