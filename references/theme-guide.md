# Building a theme

A theme is a folder with a web page. The helper serves it at `http://127.0.0.1:<port>/themes/<id>/`
and the wallpaper host shows `http://127.0.0.1:<port>/`, which redirects to the active theme.

```
~/OrbitDesktop/themes/<id>/
  theme.json      manifest: id, name, description, concept, palette, uses
  index.html      the page (must load ../../sdk/orbit.js)
  style.css       layout and tokens
  scene.js        canvas or DOM animation, and the glue between events and the scene
  preview.png     made by `orbit.py snapshot <id>`
  assets/         optional images, fonts, sounds
```

Start from `orbit.py new-theme <id> --from template` (a commented skeleton) or copy an example with
`--from ink-study|deep-orbit|defrag-95`. Everything in the folder can change; the helper reloads open
pages a moment after you save a file.

## theme.json

```json
{
  "schema": 1,
  "id": "rainy-library",
  "name": { "zh-CN": "雨夜书库", "en": "Rainy Library" },
  "description": { "zh-CN": "…", "en": "…" },
  "author": "…",
  "version": "1.0.0",
  "language": "zh-CN",
  "entry": "index.html",
  "palette": { "background": "#…", "accent": "#…" },
  "concept": {
    "world": "…", "mood": "…", "type": "…", "motion": "…",
    "metaphors": { "tidy-files.run": "…", "quit-apps.run": "…", "system.battery": "…" }
  },
  "uses": { "actions": ["tidy-files", "quit-apps"], "data": ["clock", "weather", "system"] },
  "performance": { "fps": 24 }
}
```

`id` uses a-z, 0-9 and `-`, and matches the folder name. `name` and `description` may be plain strings or
`{ "zh-CN": …, "en": … }`. `uses.actions` must list every action the page uses (validate checks this).

## The SDK

Load it after your markup and before your own scripts:

```html
<script src="../../sdk/orbit.js"></script>
<script src="scene.js"></script>
```

Served by the helper the page is **live**: buttons run real actions. Opened any other way, or with
`?demo` in the URL, it runs in **demo** mode with sample weather, readings and simulated actions, so a
theme can always be previewed safely. `Orbit.live` / `Orbit.demo` tell you which.

### Markup bindings (no JavaScript needed)

| Attribute | Effect |
|---|---|
| `data-orbit-action="tidy-files"` | Click runs the action. Add `data-orbit-op="undo"` for another operation (default `run`). |
| `data-orbit-params='{"source":"downloads"}'` | Parameters for this button (only ones the action declares). |
| `data-orbit-confirm="auto\|always\|never"` | `auto` (default) asks for a second click when the operation closes apps or changes settings, and shows the action's `preview` message meanwhile. |
| `data-orbit-status` / `data-orbit-status="quit-apps"` | Shows the latest message (of all actions, or one). |
| `data-orbit-value="tidy-files.pending"` | A value from an action's `status` data (`pending`, `open`, `reopenable`, …). |
| `data-orbit-clock="{HH}:{mm}"` | Live clock. Tokens: `{YYYY} {MM} {M} {DD} {D} {HH} {H} {hh} {h} {mm} {ss} {ampm} {weekday} {wd} {month} {mon} {doy} {shichen} {cn-month} {cn-day} {cn-weekday}` |
| `data-orbit-weather="temperature"` | `temperature`, `apparent`, `high`, `low`, `condition`, `place`, `humidity`, `wind`. |
| `data-orbit-system="cpu"` | `cpu`, `memory`, `disk`, `battery` as percentages. |
| `data-orbit-gallery` | Opens the theme gallery in the browser. |

Empty values get a `data-orbit-empty` attribute, so `[data-orbit-empty] { display: none }` hides, say,
the battery row on a desktop PC.

### State you can style

On `<html>`:
`data-orbit-mode` (live, demo), `data-orbit-connection` (online, offline), `data-orbit-paused`,
`data-orbit-busy` (id of the running action), `data-daypart` (dawn, day, dusk, night),
`data-weather` (clear, partly, cloudy, fog, drizzle, rain, snow, storm), `data-os` (windows, macos, linux),
and CSS custom properties `--orbit-cpu`, `--orbit-memory`, `--orbit-disk`, `--orbit-battery` (0 to 1).
Use them directly, for example `width: calc(var(--orbit-cpu, 0) * 100%)`.

On action elements: `is-running`, `is-done`, `is-error` (about 2.6 s), `is-armed` (waiting for the
confirming click), `is-unavailable` (the action's status says this operation has nothing to do).

### JavaScript

```js
Orbit.ready.then(() => { /* state, weather, readings and statuses are loaded */ });

Orbit.on('action', (e) => {
  // e.action, e.op, e.phase: 'start' | 'progress' | 'done' | 'error'
  // progress events carry e.progress (0..1), e.message and action-specific fields:
  //   tidy-files: e.item, e.category, e.status ('moved' | 'keep' | 'restored')
  //   quit-apps:  e.app, e.status ('closed' | 'hidden' | 'waiting' | 'opened')
  // done/error carry e.result = { ok, message, data }
});
Orbit.on('confirm', (e) => { /* e.phase 'armed' (with e.preview) or 'cancel' */ });
Orbit.on('status', (e) => { /* e.action, e.data, e.g. e.data.pending */ });
Orbit.on('weather', (w) => {}); Orbit.on('system', (s) => {}); Orbit.on('daypart', ({ daypart }) => {});
Orbit.on('pause', () => {}); Orbit.on('resume', () => {}); Orbit.on('connection', ({ online }) => {});

Orbit.run('tidy-files', 'run', {});            // what a button does; resolves to { ok, message, data }
Orbit.query('quit-apps', 'preview');           // read-only data, no UI side effects
Orbit.loop((t, dt) => draw(t, dt), { fps: 24 }); // pauses when hidden; t = seconds of visible animation
Orbit.t('中文', 'English');                     // pick text for the user's language (Orbit.lang is 'zh' or 'en')
Orbit.formatDate(new Date(), '{HH}:{mm}');
Orbit.pointer                                   // { x, y } in 0..1 for subtle parallax
Orbit.progressPace = 160;                       // ms between progress events (they are paced so fast runs still animate)
```

## Layout rules

- The page fills the screen: `html, body { height: 100%; margin: 0; overflow: hidden }`.
- Keep the desktop-icon side calm. The examples use
  `:root[data-os="windows"] { --safe-left: 112px } :root[data-os="macos"] { --safe-right: 118px }` and place
  panels with `right: calc(var(--safe-right) + 4vw)`.
- Leave the bottom ~6% for the taskbar or Dock.
- Size with `vh`/`vw` so it scales from 1366×768 to 4K. For pixel-art worlds, draw at 1995 sizes and
  scale the whole stage with `transform: scale(var(--z))` (see `defrag-95`).
- A canvas scene: size it to `innerWidth × innerHeight × min(devicePixelRatio, 2)`, and fall back to
  `screen.width/height` when the window reports 0 while the wallpaper host starts.

## Patterns from the examples

- **Bilingual labels:** write the main language in the markup and the other in `data-en` / `data-zh`;
  swap them in scene.js at start-up (see `ink-study` and `defrag-95`).
- **Vertical Chinese text:** `writing-mode: vertical-rl` on inner spans (not on the button itself);
  digits upright with `text-combine-upright: all`.
- **Counts as objects:** listen to `status` and keep as many objects as `e.data.pending` (debris) or
  `e.data.open` (satellites).
- **Per-item progress:** spawn one animated object per `progress` event; finish with an effect on `done`.
- **Confirm in the world's language:** listen to `confirm` and render `e.preview.data.apps` (Close Program list in `defrag-95`).

## Checking a theme

```
orbit.py validate <id>                       # manifest, SDK tag, actions exist, reduced motion, size
orbit.py snapshot <id>                       # writes preview.png using demo data
orbit.py snapshot <id> --size 1366x768 --out small.png
orbit.py open <id> --window                  # look at it live
```

URL switches for previews: `?demo` (sample data), `?daypart=night|dawn|dusk|day`,
`?weather=rain|snow|fog|clear`, `?lang=en|zh`, `?snapshot` (no live connection, used by snapshots).
