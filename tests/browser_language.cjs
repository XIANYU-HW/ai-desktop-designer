// Optional language acceptance: NODE_PATH=<Playwright packages> node tests/browser_language.cjs
// Serve the repository at 127.0.0.1:49630 first. All storage is in disposable browser contexts.
// ORBIT_DEMO_BASE, ORBIT_CHROME and ORBIT_BROWSER_REPORT match browser_showcases.cjs.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const base = (process.env.ORBIT_DEMO_BASE || 'http://127.0.0.1:49630').replace(/\/$/, '');
const out = process.env.ORBIT_BROWSER_REPORT || fs.mkdtempSync(path.join(os.tmpdir(), 'orbit-language-'));
const storageKey = 'ai-desktop-designer-showcase-language';
const themeIds = ['deep-orbit', 'defrag-95', 'genshin-sumeru', 'ink-study', 'threebody-observatory'];
const results = { base, checks: [], captures: [], errors: [], notes: ['Public showcase and demo pages only; no native hosts or system actions.'] };
fs.mkdirSync(out, { recursive: true });
function check(label, condition) { results.checks.push({ label, passed: !!condition }); assert.ok(condition, label); }

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ORBIT_CHROME ? { executablePath: process.env.ORBIT_CHROME } : { channel: 'chrome' }) });
  try {
    async function context(options = {}) {
      const c = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'en-US', ...options });
      c.on('page', p => p.on('pageerror', e => results.errors.push(e.message)));
      return c;
    }
    async function open(c, query = '') {
      const p = await c.newPage();
      await p.goto(base + '/' + query, { waitUntil: 'networkidle' });
      await p.evaluate(() => document.fonts.ready);
      return p;
    }
    async function links(p, language, label) {
      const entries = await p.locator('a[href^="themes/"]').evaluateAll(nodes => nodes.map(a => ({ url: a.href, id: new URL(a.href).pathname.split('/themes/')[1].split('/')[0] })));
      check(label + ': all five themes are linked', JSON.stringify([...new Set(entries.map(a => a.id))].sort()) === JSON.stringify(themeIds));
      check(label + ': every demo link carries language and demo mode', entries.every(a => { const q = new URL(a.url).searchParams; return q.get('lang') === language && q.get('demo') === '1'; }));
      const install = new URL(await p.locator('[data-install-link]').getAttribute('href'));
      check(label + ': installation guide follows language', language === 'en' ? install.pathname === '/XIANYU-HW/ai-desktop-designer' && install.hash === '#get-started' : install.pathname.endsWith('/README.zh-CN.md') && decodeURIComponent(install.hash) === '#开始使用');
    }
    async function localized(p, language, label) {
      const zh = language === 'zh-CN';
      check(label + ': document language', await p.getAttribute('html', 'lang') === language);
      check(label + ': toggle state', await p.locator('[data-set-lang="' + language + '"]').getAttribute('aria-pressed') === 'true' && await p.locator('[data-set-lang][aria-pressed="true"]').count() === 1);
      check(label + ': headline is translated', (await p.locator('[data-i18n="hero-title"]').textContent()).includes(zh ? '把你想象的世界' : 'A world you love.'));
      const metadata = await p.evaluate(() => ({ title: document.title, ogTitle: document.querySelector('meta[property="og:title"]').content, description: document.querySelector('meta[name="description"]').content, social: document.querySelector('meta[property="og:description"]').content, image: document.querySelector('meta[property="og:image"]').content }));
      check(label + ': title and social title agree', metadata.title === metadata.ogTitle && metadata.title.includes(zh ? '让桌面成为一个世界' : 'A desktop you can live in'));
      check(label + ': description and social description follow language', [metadata.description, metadata.social].every(s => /[\u3400-\u9fff]/.test(s) === zh));
      check(label + ': social image follows language', metadata.image.endsWith(zh ? '/themes/genshin-sumeru/preview.png' : '/docs/showcase/genshin-en.png'));
      check(label + ': accessible image/navigation copy follows language', await p.locator('nav').getAttribute('aria-label') === (zh ? '主导航' : 'Main navigation') && /[\u3400-\u9fff]/.test(await p.locator('#garden-image').getAttribute('alt')) === zh);
      await links(p, language, label);
    }

    // Each locale gets a fresh context: no prior preference can mask browser detection.
    for (const [locale, expected] of [['en-US', 'en'], ['zh-CN', 'zh-CN'], ['zh-TW', 'zh-CN'], ['fr-FR', 'en']]) {
      const c = await context({ locale }), p = await open(c);
      await localized(p, expected, 'Fresh ' + locale);
      await c.close();
    }
    // Both browser and stored preference disagree with the explicit URL choice.
    for (const [locale, saved, query] of [['zh-CN', 'zh-CN', 'en'], ['en-US', 'en', 'zh-CN']]) {
      const c = await context({ locale });
      await c.addInitScript(({ key, value }) => {
        // newPage also runs this on about:blank, which has no storage origin.
        if (location.origin !== 'null') localStorage.setItem(key, value);
      }, { key: storageKey, value: saved });
      const p = await open(c, '?lang=' + query);
      await localized(p, query, 'URL beats storage and ' + locale);
      await c.close();
    }

    const c = await context({ locale: 'zh-CN' }), p = await open(c, '?lang=en');
    const englishCopy = await p.locator('[data-i18n]').evaluateAll(nodes => nodes.map(n => ({ key: n.dataset.i18n, text: n.textContent })));
    check('Translation coverage is substantial', englishCopy.length >= 40);
    for (const language of ['zh-CN', 'en']) {
      await p.locator('[data-set-lang="' + language + '"]').click();
      await localized(p, language, 'Manual ' + language);
      const copy = await p.locator('[data-i18n]').evaluateAll(nodes => nodes.map(n => ({ key: n.dataset.i18n, text: n.textContent })));
      check('All localized copy switches/restores ' + language, copy.length === englishCopy.length && copy.every((entry, i) => entry.key === englishCopy[i].key && entry.text.trim() && !/undefined|null/.test(entry.text) && (language === 'en' ? entry.text === englishCopy[i].text : entry.text !== englishCopy[i].text)));
      check('Manual choice updates URL ' + language, new URL(p.url()).searchParams.get('lang') === language);
      check('Manual choice is stored ' + language, await p.evaluate(key => localStorage.getItem(key), storageKey) === language);
      await p.reload({ waitUntil: 'networkidle' });
      await localized(p, language, 'Reload after manual ' + language);
      const fresh = await open(c);
      check('Unparameterized visit restores ' + language, !new URL(fresh.url()).searchParams.has('lang') && await fresh.getAttribute('html', 'lang') === language);
      await fresh.close();
    }

    // Keep the chosen state, changing only its language-specific screenshot.
    for (const image of ['cosmos-image', 'garden-image']) await p.locator('[data-image="' + image + '"][aria-pressed="false"]').click();
    for (const language of ['zh-CN', 'en']) {
      await p.locator('[data-set-lang="' + language + '"]').click();
      for (const [image, stem] of [['cosmos-image', 'threebody-comparison'], ['garden-image', 'genshin-bloom']]) {
        const file = 'docs/showcase/' + stem + (language === 'en' ? '-en' : '') + '.png';
        await p.waitForFunction(({ id, ending }) => { const im = document.getElementById(id); return im.src.endsWith(ending) && im.complete && im.naturalWidth > 0; }, { id: image, ending: file });
        check(image + ': state survives ' + language, (await p.locator('[data-image="' + image + '"][aria-pressed="true"]').getAttribute('data-src')).endsWith(file));
      }
    }

    for (const language of ['en', 'zh-CN']) {
      await p.locator('[data-set-lang="' + language + '"]').click();
      for (const width of [1440, 390, 320]) {
        await p.setViewportSize({ width, height: 1000 });
        await p.locator('details').evaluate(el => { el.open = true; });
        check(language + ' layout has no horizontal overflow at ' + width, await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        check(language + ' language controls fit at ' + width, await p.locator('[data-set-lang]').evaluateAll(nodes => nodes.every(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth; })));
        const target = path.join(out, 'landing-' + language + '-' + width + '.png');
        await p.screenshot({ path: target, fullPage: true }); results.captures.push(target);
      }
    }
    await p.close(); await c.close();

    // Storage denial must not break the switch or explicit URL-based refresh.
    const denied = await context();
    await denied.addInitScript(() => Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new DOMException('Storage disabled for acceptance test', 'SecurityError'); } }));
    const dp = await open(denied);
    for (const language of ['zh-CN', 'en']) {
      await dp.locator('[data-set-lang="' + language + '"]').click();
      await localized(dp, language, 'Storage denied ' + language);
      check('Storage denied: URL preserves ' + language, new URL(dp.url()).searchParams.get('lang') === language);
      await dp.reload({ waitUntil: 'networkidle' });
      check('Storage denied: reload preserves ' + language, await dp.getAttribute('html', 'lang') === language);
    }
    await denied.close();

    // Follow the actual featured links; do not construct demo URLs or trigger system controls.
    const demos = await context({ locale: 'zh-CN' });
    for (const [theme, title, heading, tool] of [
      ['threebody-observatory', 'Three-Body Observatory', 'THREE-BODY', 'Civilization archive'],
      ['genshin-sumeru', 'Sumeru · Garden of Knowledge', 'Sumeru', 'Secret archive']
    ]) {
      const demo = await open(demos, '?lang=en');
      await demo.locator('a.enter[href*="' + theme + '"]').click();
      await demo.waitForFunction(() => window.Orbit && Orbit.ready);
      await demo.evaluate(async () => { await Orbit.ready; await document.fonts.ready; });
      check(theme + ': English link reaches demo', await demo.evaluate(() => Orbit.demo && Orbit.lang === 'en') && new URL(demo.url()).searchParams.get('lang') === 'en');
      check(theme + ': English document and tab title', await demo.getAttribute('html', 'lang') === 'en' && await demo.title() === title);
      check(theme + ': heading and tool are English', (await demo.locator('h1').textContent()).includes(heading) && (await demo.locator('body').innerText()).includes(tool));
      await demo.close();
    }
    await demos.close();

    const noJS = await context({ javaScriptEnabled: false, locale: 'zh-CN' }), fallback = await open(noJS);
    check('No JavaScript: English document remains', await fallback.getAttribute('html', 'lang') === 'en');
    check('No JavaScript: hero, feature and installation copy readable', (await fallback.locator('h1').innerText()).includes('A world you love.') && await fallback.getByText('Enter the observatory', { exact: false }).isVisible() && await fallback.getByText('Get started', { exact: false }).isVisible());
    await links(fallback, 'en', 'No JavaScript');
    await fallback.setViewportSize({ width: 320, height: 1000 });
    check('No JavaScript: 320px layout does not overflow', await fallback.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await noJS.close();
    check('No browser script errors', results.errors.length === 0);
  } catch (error) {
    results.failure = error.stack || String(error); throw error;
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(out, 'language-acceptance.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify({ report: out, checks: results.checks.length, passed: results.checks.filter(c => c.passed).length, errors: results.errors, failure: results.failure || null }, null, 2));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
