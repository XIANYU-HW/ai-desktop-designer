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
context. `--publish-assets` additionally refreshes the four Chinese screenshots. The English presentation uses
separate captures of the same pages and states with `lang=en`, listed below.

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
| [Three-Body overview, English](showcase/threebody-en.png) | Actual theme, `demo=1&snapshot=1&lang=en&review=600`, 1920×1080 |
| [Three-Body comparison, English](showcase/threebody-comparison-en.png) | Same English capture with `review-state=comparison` |
| [Sumeru overview, English](showcase/genshin-en.png) | Actual theme, `demo=1&snapshot=1&lang=en&review=600`, 1920×1080 |
| [Sumeru bloom, English](showcase/genshin-bloom-en.png) | Same English capture with `review-state=bloom` |

Background illustrations were generated with the built-in image tool; all text, widgets and controls
in these screenshots are rendered by the theme code. See [artwork provenance and prompts](showcase-art.md).
The source artwork has been retained. No personal desktop screenshot is published.

## International presentation

The default GitHub README is a complete English introduction. [简体中文](../README.zh-CN.md)
retains the Chinese version, with matching-language screenshot and demo links in both documents.
The public showcase has an English HTML fallback and a language switch. Selection priority is an
explicit `lang=en` / `lang=zh-CN` URL, a saved manual choice, then the browser's primary language.
Chinese browser languages use Simplified Chinese; other unsupported languages fall back to English.
The switch updates text, metadata, image states and all theme links. A manual choice is also kept in
the URL so refresh still works when browser storage is unavailable.

With the same local server and Playwright setup, run the focused language check:

```sh
node tests/browser_language.cjs
```

The focused run passed 162 assertions with no page-script errors, including six viewport/language captures.
It exercises language detection and overrides, manual switching and persistence, matching screenshots
and links, English demo entry, narrow layouts, disabled storage and the English no-JavaScript fallback.
The four additional English theme captures were inspected at 1920×1080: all had empty script-error,
offscreen-text and overlapping-control reports, with no failed font or asset loads.
