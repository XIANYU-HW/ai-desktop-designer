# Building a theme

A theme is a folder with a web page, served at `http://127.0.0.1:<port>/themes/<id>/`. The wallpaper host
normally opens `/`, which redirects to the active theme. This web runtime is separate from an existing
native Mac ORBIT app; its source, themes and permissions do not transfer automatically.

```text
~/OrbitDesktop/themes/<id>/
  theme.json       manifest, concept and review plan
  index.html       entry page; loads ../../sdk/orbit.js
  style.css        layout, tokens and state styles
  scene.js         optional scene behavior and demo fixtures
  preview.png      generated preview
  assets/          optional art, fonts, video, sounds
```

Use `new-theme <id> --from template` or `--from ink-study|deep-orbit|defrag-95`. Preserve an existing
version before editing. The template is a static skeleton with clock/weather, no preselected actions,
and working empty/offline fixtures. Replace its composition, data and visual language as needed. A
saved change can reload open live pages, so preserve unsent input before enabling that behavior in a
companion window.

## Manifest and authoring notes

```json
{
  "schema": 1,
  "id": "quiet-workspace",
  "name": { "zh-CN": "静谧工作台", "en": "Quiet Workspace" },
  "description": "A restrained workspace with the user's chosen tools.",
  "version": "0.1.0",
  "language": "zh-CN",
  "entry": "index.html",
  "palette": { "background": "#f2f1ed", "text": "#272a29", "accent": "#355f54" },
  "concept": {
    "world": "A quiet work surface; no fictional setting required.",
    "mood": "Calm and legible.",
    "type": "Deliberate system typography with stable numerals.",
    "motion": "Static ambient scene; brief event feedback only.",
    "metaphors": {}
  },
  "requirements": [
    { "id": "R1", "request": "Open the project folder", "implementation": "project control / open-path", "verification": "preview parameters and authorized open result" }
  ],
  "uses": { "actions": ["open-path"], "data": ["clock"] },
  "performance": { "mode": "static", "fps": 0 },
  "review": { "states": { "empty": "review-state=empty", "offline": "review-state=offline" } }
}
```

IDs use 2–48 lowercase letters, digits and hyphens and should match their folder. Localized `name` and
`description` accept strings or language maps. List used actions in `uses.actions`; validate checks
statically detectable references. `concept`, `requirements` and `performance` document design choices;
they do not enforce behavior or automatically configure CSS/frame rates. Keep them consistent with code.
`review.states` declares query fixtures which the theme must implement; it is not an action trigger.

## Fonts and assets

Use assets suited to the art direction. Bundle licensed fonts when repeatable rendering requires them;
intentional system fonts are also valid, with platform inspection. To download Google Fonts subsets:

```text
orbit.py fonts <id> --family "Noto Serif SC" --weights 400 --name "Reading Serif" --chars common-zh
orbit.py fonts <id> --family "Cormorant Garamond" --weights 400,500 --name "Display Serif" --script latin
```

Link `assets/fonts/fonts.css` before the theme stylesheet and use the selected family name. Regenerate
subsets after text changes. `common-zh` adds GB2312 level-one characters and punctuation; it is not all
Chinese or every character a user may enter. Dynamic names, rare characters and other languages need
appropriate coverage and intentional fallbacks. Inspect actual glyphs; a loaded font file alone does
not prove coverage. Record asset provenance and usage terms when relevant, especially for sharing.

## SDK and modes

Load after markup and before theme scripts:

```html
<script src="../../sdk/orbit.js"></script>
<script src="scene.js"></script>
```

When the helper supplies a token the page is **live** and controls can run real operations. `?demo=1`
forces SDK sample data and simulated actions. `snapshot` is a capture hint, not a replacement for demo
mode; use both for safe review. Custom JavaScript can bypass the SDK, so imported code and fixtures
still need review. Built-in demo responses do not validate custom action behavior.

| Binding | Effect |
|---|---|
| `data-orbit-action="open-path"` | Click runs an action; `data-orbit-op` selects the operation (default `run`). |
| `data-orbit-params='{"path":"{documents}/Projects"}'` | Declared action parameters for the control. |
| `data-orbit-confirm="auto\|always\|never"` | SDK confirmation policy; auto arms app/system operations. Choose according to effect and authorization; do not use presentation settings as a security guarantee. |
| `data-orbit-status` or `data-orbit-status="ACTION"` | Latest all-action or action-specific message. |
| `data-orbit-value="ACTION.FIELD"` | A value from action status data. |
| `data-orbit-clock="{HH}:{mm}"` | Date/time format tokens listed below. |
| `data-orbit-weather="temperature"` | Also apparent, high, low, condition, place, humidity, wind. |
| `data-orbit-system="cpu"` | Also memory, disk and battery percentages. |
| `data-orbit-gallery` | Open the theme gallery. |

Clock tokens: `{YYYY} {MM} {M} {DD} {D} {HH} {H} {hh} {h} {mm} {ss} {ampm} {weekday} {wd} {month}
{mon} {doy} {shichen} {cn-month} {cn-day} {cn-weekday}`. Empty bindings get `data-orbit-empty`; design
whether to hide them or show a meaningful unavailable label.

The root exposes `data-orbit-mode`, `data-orbit-connection`, `data-orbit-paused`, `data-orbit-busy`,
`data-daypart`, `data-weather`, `data-os` and normalized `--orbit-cpu/memory/disk/battery` CSS properties.
Action controls use `is-running`, `is-done`, `is-error`, `is-armed`, `is-unavailable`. Style applicable
states without relying on color alone. State classes are presentation, not evidence of an OS effect.

```js
Orbit.ready.then(() => { /* initial data available */ });
Orbit.on('action', e => {
  // e.action, e.op, e.phase: start | progress | done | error
  // progress: e.progress, e.message, and action-specific fields
  // done/error: e.result = { ok, message, data }
});
Orbit.on('confirm', e => { /* e.phase: armed | cancel; e.preview when available */ });
Orbit.on('status', e => { /* e.action, e.data */ });
Orbit.on('weather', w => {}); Orbit.on('system', s => {});
Orbit.on('daypart', e => {}); Orbit.on('connection', e => {});
Orbit.on('pause', () => {}); Orbit.on('resume', () => {});
Orbit.query('tidy-files', 'preview', {}); // read-only, no UI side effects
Orbit.run('open-path', 'run', {path: '{documents}/Projects'}); // real effect when live
Orbit.t('中文', 'English');
Orbit.formatDate(new Date(), '{HH}:{mm}');
// Only for a scene that needs continuous motion; choose its budget:
const animation = Orbit.loop((t, dt) => draw(t, dt), {fps: 30});
// animation.stop() releases this loop; Orbit.pointer exposes x/y/active.
```

SDK action events can be paced for presentation (`Orbit.progressPace`, default 160 ms); do not confuse
animation duration with operation duration. Bound effects and verify final results separately. For
reduced motion, prefer an explicit still/reduced effect when simple frame throttling is unsuitable.

## Layout and host capabilities

Fill the viewport and use responsive constraints suited to the composition. Example safe margins
(`--safe-left: 112px` on Windows, `--safe-right: 118px` on macOS, bottom 6%) are starting assumptions;
check actual icon placement, multiple monitors, scaling and Dock/taskbar position. A browser's outer
window size can differ from its content viewport: inspect the report's measured viewport.

Cache expensive static layers; cap canvas rendering size and pixel ratio according to measured cost.
DOM, CSS, SVG, canvas, media and shaders have different host compatibility and pause behavior. Test the
chosen implementation; do not infer Plash behavior from Chromium or native Swift behavior from Plash.

| Surface | Input/verification implication |
|---|---|
| Lively on Windows | Mouse forwarding and keyboard settings depend on host configuration. Check focus, typing and IME on the actual setup before relying on them. |
| Plash on macOS | Interactivity uses Browsing Mode; verify focus, keyboard/IME and return to desktop behavior in Plash. |
| Browser companion window | Can provide normal text input. Test IME, focus, opening/closing and draft recovery in the chosen browser. |
| Existing native Mac ORBIT | Separate application with its own controls/bridge. Preserve it by default; this helper does not manage or verify its behavior. |

### Text input and AI integration

If wallpaper input is unavailable or inconvenient, implement a companion window appropriate to the
task; full screen is optional. `hosts.quiet_profile()` and `hosts.browser_window_args()` are available
for a dedicated Chromium profile and app window. Do not change the user's ordinary browser profile.
Keep `translate="no"`, the correct page language and `notranslate` metadata. These reduce prompts but
require actual first/repeat-launch checks; flags and screenshots of headless pages do not inspect chrome.

Keep text when focus moves elsewhere. Do not close on blur, clear on launch failure or discard text
before confirmed handoff. Define draft persistence, privacy and explicit clearing; preserve input
through theme reloads when a live page can reload. Test Chinese composition/paste, empty/long text,
blur/return, close/reopen, repeated submit and destination failure.

No AI bridge or model is built in. If requested, create an integration for the actual destination and
its supported mechanisms. Distinguish local draft, destination opened, message sent and reply received.
Respect authorization for sending, and verify the actual destination state. If only a draft can be
opened, label the result accordingly and keep a recovery copy.

## Review fixtures

Use `review-state=<name>` for a theme-owned deterministic fixture. The template implements `empty`
and `offline`; extend it only for actual features. Each handler must:

1. Require `Orbit.demo`, run after initial data/render setup, and never call a real effect.
2. Feed representative fixture data through the component's rendering path where practical.
3. Set `document.documentElement.dataset.reviewState` to the applied name only after the state is set.
4. Leave a stable meaningful capture point; label simulated behavior and report unsupported states.

```js
Orbit.ready.then(() => {
  const state = new URLSearchParams(location.search).get('review-state');
  if (!Orbit.demo || !state) return;
  if (state === 'empty') {
    renderItems([]); // theme-owned renderer, also used for actual data
    document.documentElement.dataset.reviewState = state;
  }
});
```

Declare only implemented cases, e.g. `"review": {"states": {"empty": "review-state=empty"}}`.
The marker proves only that the handler declared the state; inspect the image and expected content too.
Action themes need applicable armed, running, done, error, canceled, partial and recovery cases. Input
themes need typing and handoff-error states. Query fixtures verify presentation; separately test real
transitions in demo mode and action behavior on isolated data.

```text
orbit.py validate <id>
orbit.py snapshot <id> --size 1366x768 --query review-state=empty
orbit.py review <id>
orbit.py open <id> --window
```

Built-in preview queries: `demo`, `daypart=night|dawn|dusk|day`, `weather=rain|snow|fog|clear`,
`lang=en|zh`, `snapshot`, and `review`. The last collects page measurements. Use
[quality-review.md](quality-review.md) for actual image inspection, motion/interaction checks and host
evidence. A successful render is not visual approval or proof of a working integration.
