// Optional browser acceptance: NODE_PATH=<Playwright packages> node tests/browser_showcases.cjs
// Serve the repo root on 127.0.0.1:49630 first. Only demo pages are opened.
// --publish-assets writes actual browser screenshots used by README and the gallery.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const root=path.resolve(__dirname,'..');
const base=(process.env.ORBIT_DEMO_BASE||'http://127.0.0.1:49630').replace(/\/$/,'');
const out=process.env.ORBIT_BROWSER_REPORT||fs.mkdtempSync(path.join(os.tmpdir(),'orbit-showcase-'));
fs.mkdirSync(out,{recursive:true});
const publish=process.argv.includes('--publish-assets');
const results={base,checks:[],captures:[],errors:[],notes:['Browser demo only. Native hosts and device energy use are not certified.']};
function check(label,condition){assert.ok(condition,label);results.checks.push(label)}
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.ORBIT_CHROME?{executablePath:process.env.ORBIT_CHROME}:{channel:'chrome'})});
 try{
  const context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  async function open(id,query='',size={width:1920,height:1080}){
   const p=await context.newPage();await p.setViewportSize(size);
   p.on('pageerror',e=>results.errors.push(id+': '+e.message));
   const params=new URLSearchParams(query.replace(/^&/,''));params.set('demo','1');if(!params.has('lang'))params.set('lang','zh-CN');
   await p.goto(base+'/themes/'+id+'/?'+params.toString(),{waitUntil:'networkidle'});
   await p.evaluate(()=>document.fonts.ready);
   check(id+' is demo',await p.evaluate(()=>Orbit.demo===true));
   return p;
  }
  for(const id of ['threebody-observatory','genshin-sumeru']){
   const manifest=JSON.parse(fs.readFileSync(path.join(root,'themes',id,'theme.json'),'utf8'));
   for(const [label,size,lang] of [
    ['desktop',{width:1920,height:1080},'zh-CN'],
    ['compact',{width:1366,height:768},'zh-CN'],
    ['wide',{width:2560,height:1080},'en'],
    ['portrait',{width:1280,height:1024},'zh-CN'],
    ['small',{width:1024,height:768},'en']]){
    const p=await open(id,'&snapshot=1&review=600&lang='+lang,size);
    await p.waitForSelector('#orbit-review',{state:'attached'});
    const report=await p.locator('#orbit-review').evaluate(el=>JSON.parse(el.textContent));
    check(id+' '+label+' no script errors',report.errors.length===0);
    check(id+' '+label+' no offscreen text',report.offscreen.length===0);
    check(id+' '+label+' no overlapping controls',report.overlaps.length===0);
    const dest=publish&&label==='desktop'?path.join(root,'themes',id,'preview.png'):path.join(out,id+'-'+label+'.png');
    await p.screenshot({path:dest});results.captures.push({id,label,size,path:dest,report});
    await p.close();
   }
   for(const state of Object.keys(manifest.review.states)){
    const p=await open(id,'&snapshot=1&review-state='+state+'&review=600');
    await p.waitForSelector('#orbit-review',{state:'attached'});
    check(id+' fixture '+state,await p.getAttribute('html','data-review-state')===state);
    const r=await p.locator('#orbit-review').evaluate(el=>JSON.parse(el.textContent));
    check(id+' fixture '+state+' no errors',r.errors.length===0);
    check(id+' fixture '+state+' no overlaps',r.overlaps.length===0);
    if(state==='comparison'||state==='bloom'){
     const dest=publish?path.join(root,'docs','showcase',state==='comparison'?'threebody-comparison.png':'genshin-bloom.png'):path.join(out,id+'-'+state+'.png');
     fs.mkdirSync(path.dirname(dest),{recursive:true});await p.screenshot({path:dest});results.captures.push({id,label:state,path:dest,report:r});
    }
    await p.close();
   }
  }
  let p=await open('threebody-observatory');
  const time=await p.evaluate(()=>ThreebodyObservatory.inspect().sceneTime);
  await p.waitForTimeout(250);check('threebody ambient motion',await p.evaluate(t=>ThreebodyObservatory.inspect().sceneTime!==t,time));
  await p.click('#epoch-chaos');check('epoch changes by click',await p.getAttribute('html','data-epoch')==='chaos');
  await p.click('#compare');check('comparison toggles',await p.getAttribute('#compare','aria-pressed')==='true');
  await p.click('#freeze');const frozen=await p.evaluate(()=>ThreebodyObservatory.inspect().sceneTime);await p.waitForTimeout(200);
  check('freeze stops time',await p.evaluate(t=>ThreebodyObservatory.inspect().sceneTime===t,frozen));
  await p.click('#focus-toggle');await p.waitForTimeout(1100);check('focus timer counts',await p.textContent('#focus-time')!=='25:00');
  await p.click('#focus-toggle');const remaining=await p.textContent('#focus-time');await p.waitForTimeout(1100);check('focus pause holds',await p.textContent('#focus-time')===remaining);
  await p.click('#focus-reset');check('focus resets',await p.textContent('#focus-time')==='25:00');
  await p.click('#archive');check('tidy asks first',await p.locator('#archive').evaluate(e=>e.classList.contains('is-armed')));
  await p.click('#archive');await p.waitForFunction(()=>document.querySelector('#archive').classList.contains('is-done'));check('demo tidy completes',true);
  await p.close();
  p=await open('genshin-sumeru');
  await p.click('[data-element="hydro"]');await p.click('#resonance-point');
  check('hydro response',await p.evaluate(()=>SumeruGarden.metrics().element==='hydro'&&SumeruGarden.metrics().activeReactions>0));
  for(let i=0;i<6;i++)await p.click('#resonance-point');
  check('reaction count bounded',await p.evaluate(()=>SumeruGarden.metrics().activeReactions<=3));
  await p.click('#note-toggle');await p.fill('#note-text','记录一束树冠间的光。\nBrowser acceptance note.');
  await p.click('#note-close');await p.click('#note-toggle');
  check('note survives close',await p.inputValue('#note-text')==='记录一束树冠间的光。\nBrowser acceptance note.');
  await p.reload({waitUntil:'networkidle'});await p.click('#note-toggle');check('note survives reload',await p.inputValue('#note-text')==='记录一束树冠间的光。\nBrowser acceptance note.');
  await p.click('#note-clear');check('note explicit clear',await p.inputValue('#note-text')==='');
  await p.close();
  for(const id of ['threebody-observatory','genshin-sumeru']){
   const reduced=await browser.newContext({viewport:{width:1366,height:768},reducedMotion:'reduce'});
   const rp=await reduced.newPage();await rp.goto(base+'/themes/'+id+'/?demo=1',{waitUntil:'networkidle'});
   check(id+' reduced motion respected',await rp.evaluate(()=>window.ThreebodyObservatory?ThreebodyObservatory.inspect().reducedMotion&&ThreebodyObservatory.inspect().frozen:SumeruGarden.metrics().reducedMotion&&!SumeruGarden.metrics().animated));
   await reduced.close();
  }
  // Landing page links and image-switch controls, both narrow and desktop.
  p=await context.newPage();await p.goto(base+'/',{waitUntil:'networkidle'});
  for(const size of [{width:1440,height:1000},{width:390,height:844}]){
   await p.setViewportSize(size);
   check('landing no overflow '+size.width,await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await p.screenshot({path:path.join(out,'landing-'+size.width+'.png'),fullPage:true});
  }
  for(const target of ['cosmos-image','garden-image']){
   await p.locator('[data-image="'+target+'"][aria-pressed="false"]').first().click();
   await p.waitForFunction(id=>{const im=document.getElementById(id);return im.complete&&im.naturalWidth>0},target);
   check('landing '+target+' state image loads',true);
  }
  await p.close();await context.close();check('no browser page errors',results.errors.length===0);
 }finally{await browser.close();fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify(results,null,2));console.log(JSON.stringify({report:out,checks:results.checks.length,captures:results.captures.length,errors:results.errors},null,2))}
})().catch(e=>{console.error(e);process.exitCode=1});
