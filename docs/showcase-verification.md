# Showcase verification · 2026-10-07

## What was actually checked

This records the featured web themes and GitHub presentation. It does not certify an installation in
Plash or Lively. No existing native Mac desktop, user files, login items or running user applications
were changed by the showcase checks.

| Layer | Result |
|---|---|
| Python unit/integration suite on macOS, Python 3.9 | 102 tests run: 100 passed, 2 platform-dependent skips |
| Reproducible Chrome browser acceptance | 159 checks passed, 12 captured theme views, no page errors |
| Default layouts | Each theme at 1920×1080, 1366×768, 1280×1024 (Chinese), 2560×1080 and 1024×768 (English) |
| Review fixtures | All 12 declared states in each theme rendered and marked at 1920×1080; no script errors or overlapping controls |
| Theme assets | Fonts loaded; no missing named font family in the 12 captured reports; actual rendered artwork and controls inspected |
| Three-body interaction | Epoch switch, comparison, freeze, pointer perturbation, timer start/pause/reset/completion, live timer reload recovery, demo timer isolation and reduced-motion still state |
| Sumeru interaction | Element selection and reaction; three-reaction cap; Chinese/English note typing, close/reopen/reload, explicit clear; reduced-motion still state |
| System-action wiring | Theme controls exercised in demo mode; file move/undo and safe app-request logic tested separately with disposable data/mocks in the Python suite |
| Landing page | Desktop and 390px narrow layout, both state-image switches; no horizontal page overflow |
| Native desktop hosts | Not installed or visually tested in this showcase task |
| Energy/performance | Frame/canvas/effect bounds and reduced-motion behavior checked; no CPU, GPU, battery or universal smoothness claim |

A review fixture is a reproducible visual state, not proof that a real file move or application quit
occurred. Public demos use sample weather, file and application data. Sumeru demo notes have a separate
browser-local key; the Three-body demo timer does not read or overwrite live timer state.

## Reproduce the browser check

The browser check is an optional development tool, separate from the dependency-free Python runtime.
Provide Node.js, Playwright and Chrome, then serve the repository root:

```sh
python3 -m http.server 49630 --bind 127.0.0.1
# In another terminal, with Playwright available to Node:
node tests/browser_showcases.cjs
```

Use `ORBIT_DEMO_BASE` for another local test server, `ORBIT_CHROME` for a Chrome executable, and
`ORBIT_BROWSER_REPORT` for a report folder. The script always opens demo pages in a fresh browser
context. `--publish-assets` additionally refreshes the four real screenshots used by README and Pages.

The compact [acceptance record](showcase-acceptance.json) lists the assertions and capture dimensions.
GitHub Actions independently runs the Windows/macOS/Linux matrix and browser smoke captures;
consult the commit's [Actions results](https://github.com/XIANYU-HW/ai-desktop-designer/actions) for its current status.

## Published screenshot provenance

| Asset | Source |
|---|---|
| [Three-body overview](../themes/threebody-observatory/preview.png) | Actual theme, demo + snapshot, 1920×1080 viewport |
| [Three-body comparison](showcase/threebody-comparison.png) | Actual `comparison` fixture, same viewport |
| [Sumeru overview](../themes/genshin-sumeru/preview.png) | Actual theme, demo + snapshot, same viewport |
| [Sumeru bloom](showcase/genshin-bloom.png) | Actual `bloom` fixture, same viewport |

Background illustrations were generated with the built-in image tool; all text, widgets and controls
in these screenshots are rendered by the theme code. See [artwork provenance and prompts](showcase-art.md).
The source artwork has been retained. No personal desktop screenshot is published.
