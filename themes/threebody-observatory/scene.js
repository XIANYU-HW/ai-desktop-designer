(function () {
  'use strict';
  var root = document.documentElement;
  var zh = Orbit.lang === 'zh';
  var query = new URLSearchParams(location.search);
  var $ = function (id) { return document.getElementById(id); };
  var t = Orbit.t;
  root.lang = zh ? 'zh-CN' : 'en';
  if (!zh) {
    document.querySelectorAll('[data-en]').forEach(function (el) { el.innerHTML = el.getAttribute('data-en'); });
    document.querySelectorAll('[data-en-clock]').forEach(function (el) { el.setAttribute('data-orbit-clock', el.getAttribute('data-en-clock')); });
    document.querySelectorAll('[data-en-label]').forEach(function (el) { el.setAttribute('aria-label', el.getAttribute('data-en-label')); });
  }
  document.title = t('三体 · 文明观测站', 'Three-Body Observatory');

  function message(text) { $('status').textContent = text; }
  var canvas = $('orbits'), ctx = canvas.getContext('2d');
  var W = 1920, H = 1080, DPR = 1;
  var reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  var reduced = reducedQuery.matches;
  var epoch = 'stable', compare = false, frozen = Orbit.snapshot || reduced;
  var sceneTime = 4.8, frameClock = 0, frameLoop = null, lastPointerPaint = 0;
  var pointer = { active: false, x: 0.64, y: 0.38 };
  var pulses = [], archiveProgress = 0, lastPerturb = 0;
  var STEP = 0.004, SAMPLES = 1600, DURATION = STEP * SAMPLES * 2;
  var colors = [[255, 206, 136], [247, 239, 217], [159, 193, 216]];

  // Equal-mass, softened Newtonian model in dimensionless units. It is a finite visual
  // demonstration of different initial conditions, not a physical prediction of a planet's eras.
  function trajectory(perturbX, perturbY) {
    var p = [{x: -.97000436, y: .24308753}, {x: .97000436, y: -.24308753}, {x: 0, y: 0}];
    var v = [{x: .466203685 + perturbX, y: .43236573 + perturbY}, {x: .466203685, y: .43236573}, {x: -.93240737 - perturbX, y: -.86473146 - perturbY}];
    var out = [], limit = 1.4;
    function acceleration() {
      return p.map(function (a, i) {
        var sum = {x: 0, y: 0};
        p.forEach(function (b, j) {
          if (i === j) return;
          var dx = b.x-a.x, dy = b.y-a.y, distance = Math.pow(dx*dx + dy*dy + .012, 1.5);
          sum.x += dx/distance; sum.y += dy/distance;
        });
        return sum;
      });
    }
    var a = acceleration();
    for (var n = 0; n < SAMPLES * 2; n++) {
      for (var i = 0; i < 3; i++) { p[i].x += v[i].x*STEP + a[i].x*STEP*STEP*.5; p[i].y += v[i].y*STEP + a[i].y*STEP*STEP*.5; }
      var next = acceleration();
      for (var j = 0; j < 3; j++) { v[j].x += (a[j].x+next[j].x)*STEP*.5; v[j].y += (a[j].y+next[j].y)*STEP*.5; }
      a = next;
      if (n % 2 === 0) {
        out.push(p.map(function (body) { limit = Math.max(limit, Math.abs(body.x), Math.abs(body.y)); return {x: body.x, y: body.y}; }));
      }
    }
    return { frames: out, limit: limit };
  }
  var reference = trajectory(0, 0);
  var chaotic = trajectory(.095, -.045);
  var current = reference;
  var commonLimit = Math.max(reference.limit, chaotic.limit);

  // Pre-render each stellar volume and halo once. No per-frame blur or unbounded particles.
  function starSprite(rgb, radius) {
    var c = document.createElement('canvas'); c.width = c.height = 384;
    var g = c.getContext('2d'), cx = 192, cy = 192;
    function rgba(alpha) { return 'rgba('+rgb.join(',')+','+alpha+')'; }
    var halo = g.createRadialGradient(cx,cy,radius*.65,cx,cy,170);
    halo.addColorStop(0,rgba(.67)); halo.addColorStop(.16,rgba(.21)); halo.addColorStop(.44,rgba(.046)); halo.addColorStop(1,rgba(0));
    g.fillStyle = halo; g.fillRect(0,0,384,384);
    var corona = g.createRadialGradient(cx,cy,radius*.82,cx,cy,radius*1.9);
    corona.addColorStop(0,rgba(.7)); corona.addColorStop(.25,rgba(.26)); corona.addColorStop(1,rgba(0));
    g.fillStyle=corona;g.beginPath();g.arc(cx,cy,radius*1.9,0,Math.PI*2);g.fill();
    var disc = g.createRadialGradient(cx-radius*.32,cy-radius*.3,1,cx,cy,radius);
    disc.addColorStop(0,'#fffdf1');disc.addColorStop(.35,'#fff4da');disc.addColorStop(.8,rgba(1));disc.addColorStop(1,'rgba('+rgb.map(function(c){return Math.round(c*.78);}).join(',')+',1)');
    g.fillStyle=disc;g.beginPath();g.arc(cx,cy,radius,0,Math.PI*2);g.fill();
    // Small deterministic surface striations stay inside the stellar disc.
    g.save();g.beginPath();g.arc(cx,cy,radius-1,0,Math.PI*2);g.clip();
    for(var k=0;k<44;k++){var phase=k*2.39996,spread=Math.sqrt(k/44)*radius*.95;g.fillStyle='rgba(156,80,30,.035)';g.beginPath();g.arc(cx+Math.cos(phase)*spread,cy+Math.sin(phase)*spread,1.2+(k%3)*.6,0,Math.PI*2);g.fill();}
    g.restore();return c;
  }
  var sprites = [starSprite(colors[0],29),starSprite(colors[1],21),starSprite(colors[2],16)];
  function position(p) {
    var scale = Math.min(W*.24, H*.29) / commonLimit;
    return {x: W*.664 + p.x*scale, y: H*.36 + p.y*scale*.86};
  }
  function sampleIndex() { return Math.min(SAMPLES-1, Math.floor(sceneTime/(STEP*2))); }
  function trail(source, index, muted) {
    var from = Math.max(0,index-245);
    for (var body=0;body<3;body++) {
      ctx.lineWidth=muted?.8:1.15;
      ctx.setLineDash(muted?[3,7]:[]);
      for(var part=0;part<5;part++) {
        var start=from+Math.floor((index-from)*part/5),end=from+Math.floor((index-from)*(part+1)/5);
        ctx.beginPath();
        for(var k=start;k<=end;k+=2){var q=position(source.frames[k][body]);if(k===start)ctx.moveTo(q.x,q.y);else ctx.lineTo(q.x,q.y);}
        ctx.strokeStyle='rgba('+colors[body].join(',')+','+((muted?.10:.15)+(part/5)*(muted?.1:.44))+')';ctx.stroke();
      }
    }
    ctx.setLineDash([]);
  }
  function draw() {
    if(!ctx)return;
    ctx.setTransform(DPR,0,0,DPR,0,0);ctx.clearRect(0,0,W,H);
    var index=sampleIndex();
    var fade=(frozen||Orbit.snapshot||reduced)?1:Math.min(1,sceneTime/.65,(DURATION-sceneTime)/.65);
    ctx.globalAlpha=Math.max(.03,fade);
    // Fine instrument arcs ground the model in the observatory's architectural ring.
    ctx.lineWidth=.6;ctx.strokeStyle='rgba(211,176,130,.12)';
    ctx.beginPath();ctx.ellipse(W*.664,H*.36,Math.min(W*.235,H*.30),Math.min(W*.235,H*.30)*.86,-.13,0,Math.PI*2);ctx.stroke();
    if(compare)trail(reference,index,true);
    trail(current,index,false);
    var size=Math.max(.64,Math.min(1.4,H/1080));
    var positions=current.frames[index].map(position);
    positions.forEach(function(p,i){ctx.drawImage(sprites[i],p.x-192*size,p.y-192*size,384*size,384*size);});
    if(pointer.active){
      var px=pointer.x*W,py=pointer.y*H,nearest=positions.reduce(function(best,p){return Math.hypot(p.x-px,p.y-py)<Math.hypot(best.x-px,best.y-py)?p:best;});
      ctx.strokeStyle='rgba(224,190,145,.38)';ctx.lineWidth=.8;ctx.setLineDash([2,5]);ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(nearest.x,nearest.y);ctx.stroke();ctx.setLineDash([]);
      ctx.beginPath();ctx.arc(px,py,14,0,Math.PI*2);ctx.moveTo(px-22,py);ctx.lineTo(px-9,py);ctx.moveTo(px+9,py);ctx.lineTo(px+22,py);ctx.moveTo(px,py-22);ctx.lineTo(px,py-9);ctx.moveTo(px,py+9);ctx.lineTo(px,py+22);ctx.stroke();
    }
    pulses.forEach(function(p){var age=frameClock-p.born;if(age<0||age>1.6)return;ctx.strokeStyle='rgba(231,185,119,'+(.4*(1-age/1.6))+')';ctx.lineWidth=1;ctx.beginPath();ctx.arc(p.x*W,p.y*H,12+age*63,0,Math.PI*2);ctx.stroke();});
    if(archiveProgress>0){ctx.strokeStyle='rgba(223,178,116,.6)';ctx.lineWidth=1.5;ctx.beginPath();ctx.ellipse(W*.664,H*.36,Math.min(W*.235,H*.30),Math.min(W*.235,H*.30)*.86,-.13,-Math.PI/2,-Math.PI/2+Math.PI*2*archiveProgress);ctx.stroke();}
    ctx.globalAlpha=1;
    $('model-time').textContent='T + '+sceneTime.toFixed(1).padStart(4,'0');
  }
  function resize(){W=window.innerWidth||1920;H=window.innerHeight||1080;DPR=Math.min(window.devicePixelRatio||1,1.5,2400/W);canvas.width=Math.round(W*DPR);canvas.height=Math.round(H*DPR);draw();}
  function updateControls(){
    root.setAttribute('data-epoch',epoch);
    $('epoch-name').textContent=epoch==='stable'?t('恒纪元','Stable era'):t('乱纪元','Chaotic era');
    $('epoch-note').textContent=epoch==='stable'?t('参考初始条件','REFERENCE CONDITIONS'):t('初始条件已微扰','PERTURBED CONDITIONS');
    ['stable','chaos'].forEach(function(mode){var el=$('epoch-'+mode),active=epoch===mode;el.classList.toggle('active',active);el.setAttribute('aria-pressed',String(active));});
    $('compare').setAttribute('aria-pressed',String(compare));
    $('freeze').setAttribute('aria-pressed',String(frozen));
    $('freeze-label').textContent=reduced?t('静态观测','Still mode'):frozen?t('继续观测','Resume'):t('冻结观测','Freeze');
    $('freeze-symbol').textContent=frozen?'▷':'Ⅱ';$('freeze').disabled=reduced;
  }
  function manageLoop(){
    if(frameLoop){frameLoop.stop();frameLoop=null;}
    if(!Orbit.snapshot&&!reduced&&!frozen){frameLoop=Orbit.loop(function(_,dt){sceneTime=(sceneTime+dt*.52)%DURATION;frameClock+=dt;pulses=pulses.filter(function(p){return frameClock-p.born<1.6;});draw();},{fps:30});}
    draw();
  }
  function setEpoch(mode){epoch=mode;current=mode==='stable'?reference:chaotic;commonLimit=Math.max(reference.limit,current.limit);sceneTime=4.8;updateControls();draw();}
  $('epoch-stable').addEventListener('click',function(){setEpoch('stable');message(t('已载入参考初始条件。有限轨迹循环演示。','Reference conditions loaded. Finite trajectory replay.'));});
  $('epoch-chaos').addEventListener('click',function(){setEpoch('chaos');message(t('初始速度已微扰。开启对照可比较共同尺度下的轨迹。','Initial velocity perturbed. Compare trajectories on a common scale.'));});
  $('compare').addEventListener('click',function(){compare=!compare;if(compare&&epoch==='stable')setEpoch('chaos');updateControls();draw();message(compare?t('细虚线为参考轨迹，实线为微扰轨迹；采用共同尺度。','Dashed reference and solid perturbed trajectories use the same scale.'):t('已隐藏参考轨迹。','Reference trajectory hidden.'));});
  $('freeze').addEventListener('click',function(){if(reduced)return;frozen=!frozen;updateControls();manageLoop();});
  var field=$('observation-field');
  field.addEventListener('pointermove',function(e){pointer.active=true;pointer.x=e.clientX/W;pointer.y=e.clientY/H;var now=performance.now();if(now-lastPointerPaint>33){lastPointerPaint=now;draw();}});
  field.addEventListener('pointerleave',function(){pointer.active=false;draw();});
  field.addEventListener('click',function(e){
    var now=performance.now();if(now-lastPerturb<600)return;lastPerturb=now;
    var x=e.detail?e.clientX/W:.67,y=e.detail?e.clientY/H:.36;
    chaotic=trajectory(.07+(x-.5)*.15,-.025+(y-.35)*.10);setEpoch('chaos');compare=true;updateControls();
    pulses.push({x:x,y:y,born:frameClock});if(pulses.length>4)pulses.shift();draw();
    message(t('已施加初始条件微扰；细虚线保留参考轨迹。','Initial conditions perturbed; the dashed reference remains.'));
  });
  function reducedChanged(e){reduced=e.matches;if(reduced)frozen=true;updateControls();manageLoop();}
  if(reducedQuery.addEventListener)reducedQuery.addEventListener('change',reducedChanged);else reducedQuery.addListener(reducedChanged);
  window.addEventListener('resize',resize);

  // A local timer uses wall-clock deadlines, so hidden/sleeping pages do not lose elapsed time.
  // Demo/snapshot/review pages neither read nor write the user's persisted timer.
  var FOCUS_MS=25*60*1000, FOCUS_KEY='orbit.threebody-observatory.focus.v1';
  var timer={remaining:FOCUS_MS,deadline:null,completed:false},tickHandle=null;
  var storageAllowed=!Orbit.demo&&!Orbit.snapshot;
  function validTimer(value){return value&&Number.isFinite(value.remaining)&&value.remaining>=0&&value.remaining<=FOCUS_MS&&(value.deadline===null||(Number.isFinite(value.deadline)&&value.deadline<=Date.now()+FOCUS_MS+1000))&&typeof value.completed==='boolean';}
  function readTimer(){if(!storageAllowed)return;try{var saved=JSON.parse(localStorage.getItem(FOCUS_KEY));if(validTimer(saved))timer=saved;}catch(_){/* blocked storage leaves a functional session timer */}}
  function saveTimer(){if(!storageAllowed)return;try{localStorage.setItem(FOCUS_KEY,JSON.stringify(timer));}catch(_){message(t('计时继续；此窗口无法保存进度，关闭后不会恢复。','Timer continues; this window cannot save progress for reopening.'));}}
  function remaining(){return timer.deadline===null?timer.remaining:Math.max(0,Math.min(FOCUS_MS,timer.deadline-Date.now()));}
  function renderTimer(){
    var ms=remaining();
    if(timer.deadline!==null&&ms===0){timer={remaining:0,deadline:null,completed:true};saveTimer();message(t('本次守望完成。留下一刻秩序，休息片刻。','Your watch is complete. Take a moment to rest.'));}
    var seconds=Math.ceil(ms/1000);$('focus-time').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');
    $('focus-toggle').textContent=timer.deadline!==null?t('暂停','Pause'):timer.completed?t('再次守望','Again'):timer.remaining<FOCUS_MS?t('继续','Resume'):t('开始守望','Begin');
    $('focus-state').textContent=timer.deadline!==null?t('专注进行中','Focus in progress'):timer.completed?t('本次守望已完成','Watch complete'):timer.remaining<FOCUS_MS?t('已暂停','Paused'):t('25 分钟专注','25-minute focus');
    $('focus-toggle').setAttribute('aria-pressed',String(timer.deadline!==null));
  }
  function manageTick(){if(tickHandle){clearInterval(tickHandle);tickHandle=null;}renderTimer();if(timer.deadline!==null&&!document.hidden&&!Orbit.paused&&!Orbit.snapshot){tickHandle=setInterval(function(){renderTimer();if(timer.deadline===null)manageTick();},1000);}}
  $('focus-toggle').addEventListener('click',function(){
    if(timer.deadline!==null){timer.remaining=remaining();timer.deadline=null;}
    else {if(timer.completed||timer.remaining<=0)timer={remaining:FOCUS_MS,deadline:null,completed:false};timer.deadline=Date.now()+timer.remaining;}
    saveTimer();manageTick();
  });
  $('focus-reset').addEventListener('click',function(){timer={remaining:FOCUS_MS,deadline:null,completed:false};saveTimer();manageTick();message(t('专注计时已重置为 25 分钟。','Focus timer reset to 25 minutes.'));});
  window.addEventListener('storage',function(e){if(e.key===FOCUS_KEY&&storageAllowed){readTimer();manageTick();}});
  document.addEventListener('visibilitychange',manageTick);Orbit.on('pause',manageTick);Orbit.on('resume',function(){manageTick();draw();});
  readTimer();manageTick();

  function detail(heading,text,items){$('detail-heading').textContent=heading;$('detail-message').textContent=text||'';$('detail-list').textContent=(items||[]).join(' · ');$('operation-detail').hidden=false;}
  Orbit.on('confirm',function(e){
    if(e.phase==='cancel'){$('operation-detail').hidden=true;return;}
    var result=e.preview||{},data=result.data||{};
    detail(t('核对操作 / 再次点击执行','REVIEW / CLICK AGAIN TO RUN'),result.message,(data.apps||data.items||[]).slice(0,8).map(function(x){return x.name||x.source||x.path||x.item||String(x);}));
  });
  Orbit.on('action',function(e){
    if(e.phase==='start'){$('operation-detail').hidden=true;archiveProgress=0;}
    if(e.action==='tidy-files'&&e.phase==='progress'){archiveProgress=Math.max(0,Math.min(1,e.progress||0));draw();}
    if(e.phase==='done'||e.phase==='error'){archiveProgress=0;draw();}
  });
  Orbit.on('connection',function(e){if(!e.online)message(t('桌面服务离线。观测与本地计时仍可使用。','Desktop service offline. Observation and the local timer remain available.'));});

  // Every declared review state changes the rendered UI. Only demo pages may apply these fixtures.
  function fixture(){
    var name=query.get('review-state');if(!Orbit.demo||!name)return;
    var archive=$('archive');
    if(name==='chaotic'){setEpoch('chaos');}
    else if(name==='comparison'){setEpoch('chaos');compare=true;updateControls();}
    else if(name==='frozen'){frozen=true;sceneTime=7.2;updateControls();manageLoop();}
    else if(name==='focus-running'){timer={remaining:19*60000+42000,deadline:Date.now()+19*60000+42000,completed:false};manageTick();}
    else if(name==='focus-done'){timer={remaining:0,deadline:null,completed:true};manageTick();}
    else if(name==='armed'){$('wind-down').classList.add('is-armed');detail(t('核对操作 / 再次点击执行','REVIEW / CLICK AGAIN TO RUN'),t('演示：将请 3 个应用正常退出，未保存内容由原应用询问。','Demo: ask 3 apps to quit normally; their own save prompts remain.'),['Notes','Preview','Music']);message(t('再点一次「静默值守」确认（演示）。','Click Silent watch again to confirm (demo).'));}
    else if(name==='running'){archive.classList.add('is-running');archiveProgress=.58;message(t('归档进行中 · 5 / 9 项（演示）','Archiving · 5 / 9 items (demo)'));}
    else if(name==='done'){archive.classList.add('is-done');$('undo').classList.remove('is-unavailable');message(t('已归档 9 项，可撤销（演示）。','9 items archived; undo available (demo).'));}
    else if(name==='error'){archive.classList.add('is-error');detail(t('归档未完成','ARCHIVE INCOMPLETE'),t('演示：目标文件夹不可写，文件未移动。','Demo: destination is not writable; files were not moved.'),[]);message(t('归档失败 · 请检查目标文件夹（演示）。','Archive failed · check destination (demo).'));}
    else if(name==='empty'){document.querySelector('[data-orbit-value="tidy-files.pending"]').textContent='0';archive.classList.add('is-unavailable');message(t('案头已净，没有需要归档的文件（演示）。','No loose files need archiving (demo).'));}
    else if(name==='offline'){root.setAttribute('data-orbit-connection','offline');message(t('桌面服务离线 · 观测与本地计时仍可使用（演示）。','Service offline · observation and local timer remain available (demo).'));}
    else if(name==='undo'){$('undo').classList.remove('is-unavailable');message(t('上次归档可撤销：9 项（演示）。','Last archive can be undone: 9 items (demo).'));}
    else {console.error('Unsupported review-state: '+name);return;}
    root.setAttribute('data-review-state',name);draw();
  }
  Orbit.ready.then(function(){fixture();});
  resize();updateControls();manageLoop();
  window.ThreebodyObservatory={
    inspect:function(){return {epoch:epoch,comparison:compare,frozen:frozen,reducedMotion:reduced,sceneTime:sceneTime,samples:current.frames.length,renderPixelRatio:DPR,frameCap:30,focus:{remaining:remaining(),running:timer.deadline!==null,completed:timer.completed},fixture:root.getAttribute('data-review-state')};}
  };
})();
