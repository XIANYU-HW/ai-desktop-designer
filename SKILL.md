---
name: orbit-desktop
description: Design and run a fully customized, living desktop on Windows or macOS where the wallpaper, animation, widgets and one-click desktop functions (tidy loose files, wind down open apps, open folders, or new functions you build) share one visual concept instead of being bolted on. Use when someone wants to customize, theme, beautify or redesign their desktop or wallpaper, add desktop widgets or buttons, create a new one-click desktop function, or install, switch or fix Orbit Desktop themes. Not for editing a single static image.
---

# Orbit Desktop

Orbit Desktop turns the desktop into one designed object. A **theme** is a web page shown as the
wallpaper (any style, motion and layout). **Actions** are small programs that do real work on the
computer (tidy files, quit apps, open folders, anything new you write). A local **helper**
(`runtime/orbit.py`, Python 3.9+, no dependencies) serves the theme to the wallpaper host and runs
actions when the theme's buttons are clicked. Windows uses the free Lively Wallpaper as host,
macOS uses Plash, and any browser works for previews.

The point of the skill is fusion: every function must become something that belongs to the
theme's world (files flying into a scroll, debris captured into orbit, a defragmenter's blocks),
driven by real data and real progress. Read `references/design-principles.md` before designing.

## Ground rules

- Speak the user's language. Theme text follows the user's language unless the world calls for another.
- Never run an operation that changes the computer (effect `files`, `apps` or `system`: e.g.
  `tidy-files run/undo`, `quit-apps run/reopen`) unless the user asked for it in this conversation.
  Use the read-only `preview` and `status` operations to check behaviour. The CLI refuses such
  operations without `--yes`.
- Ask before installing software (Python, Lively Wallpaper, Plash) and before turning on start at sign-in.
- Actions never delete files, never force-quit, never change system settings, and always offer a
  `preview`; anything that changes state should be undoable. See `references/action-guide.md`.
- Brand or fictional IP (anime, games, films) is fine for the user's own desktop; do not publish such themes.

## Running the helper

`SKILL_DIR` is the folder containing this file. Run commands with the interpreter that works on the machine:

```
python  "<SKILL_DIR>/runtime/orbit.py" <command>      # Windows (or: py -3 ...)
python3 "<SKILL_DIR>/runtime/orbit.py" <command>      # macOS / Linux
```

The user's data lives in the workspace `~/OrbitDesktop` (config.json, themes/, actions/, state/, logs/).
Bundled themes and actions are read from `SKILL_DIR`; a workspace item with the same id wins.

## Workflow

1. **Check the machine.** `orbit.py doctor`. If Python is missing on Windows, offer
   `winget install -e --id Python.Python.3.12 --scope user` (ask first). Then `orbit.py init --lang zh-CN`
   (or `en`: use the language the user writes in, not the system's UI language), `orbit.py set-location "<city>" --pick 1`
   if a city is known, and `orbit.py start`.
2. **Understand the wish in a few questions at most:** the world or mood (offer the bundled examples via
   `orbit.py gallery`), which functions they want (`orbit.py actions`), light or dark, how much motion.
   If the request is already clear, pick sensible defaults and say which.
3. **Write the concept first.** Fill `concept` in theme.json: world, mood, type, motion and a
   `metaphors` entry for every function and every piece of data the theme shows. Summarise it to the
   user in a few lines when the design is ambitious.
4. **Build the theme.** `orbit.py new-theme <id> --from template` (or `--from ink-study`, `deep-orbit`,
   `defrag-95` to start from an example), then edit `~/OrbitDesktop/themes/<id>/`. Follow
   `references/theme-guide.md`. Open pages reload by themselves when files change.
5. **Add or tune functions.** Many "new" functions are built-ins with parameters (a button can pass
   `data-orbit-params`); see `references/builtin-actions.md`. For real new behaviour:
   `orbit.py new-action <id>`, implement it per `references/action-guide.md`, then
   `orbit.py validate-action <id>` and `orbit.py run <id> preview`.
6. **Check your work by looking at it.** `orbit.py validate <id>` then `orbit.py snapshot <id>`
   and read the PNG (bundled themes are rendered to `~/OrbitDesktop/previews/`, so their shipped previews stay intact). Also snapshot with `--out` at `--size 1366x768` and `--size 2560x1440`. Fix
   overlaps with the desktop-icon area, unreadable text, empty states and clutter before showing the user.
   `orbit.py open <id> --window` shows it to the user; `?demo`, `?daypart=night`, `?weather=rain` in the
   URL preview other states.
7. **Put it on the desktop.** `orbit.py use <id>`, then `orbit.py install`. On Windows this needs Lively
   Wallpaper (`winget install -e --id rocksdanister.LivelyWallpaper`, ask first); on macOS, Plash from the
   App Store (clicks need Plash's Browsing Mode). `install` also starts the helper at sign-in. Tell the
   user how to undo: `orbit.py uninstall`. Details and manual steps: `references/hosts.md`.

## Commands

| Command | What it does |
|---|---|
| `doctor` | Report Python, workspace, helper, browser, Lively/Plash, autostart |
| `init [--lang zh-CN\|en] [--theme ID]` | Create the workspace and config |
| `start` / `stop` / `status` | Run the helper in the background, stop it, show state |
| `themes`, `use ID`, `gallery` | List, switch, or open the theme gallery |
| `new-theme ID [--from template\|THEME] [--name N]` | Create a theme in the workspace |
| `validate [ID...]`, `snapshot ID [--size WxH] [--live] [--out F]` | Check a theme; render it to PNG (demo data by default) |
| `open [ID] [--window]` | Preview in a full-screen (or normal) browser window |
| `actions`, `run ACTION [OP] [--param KEY=VALUE ...] [--yes] [--json]` | List actions; run one operation (default `preview`). Prefer repeated `--param` over `--params JSON`: Windows PowerShell strips the quotes inside JSON |
| `new-action ID`, `validate-action ID` | Create and check a custom action |
| `set-location CITY [--pick N]`, `config [KEY] [VALUE]` | Weather place; language, units, port |
| `install [--no-autostart]`, `uninstall`, `autostart on\|off\|status` | Desktop host and start at sign-in |
| `export-theme ID`, `import-theme ZIP` | Share themes (imported themes are code: trust the source) |

## References

- `references/design-principles.md`: the method for fusing function and aesthetics. Read before designing.
- `references/theme-guide.md`: theme folder, theme.json, the SDK (markup bindings, JS API, events, CSS hooks), layout and performance rules, checklist.
- `references/builtin-actions.md`: what tidy-files, quit-apps and open-path do, their operations and parameters.
- `references/action-guide.md`: writing a new, safe, cross-platform action.
- `references/hosts.md`: Lively Wallpaper, Plash, autostart, multiple monitors, desktop icons.
- `references/troubleshooting.md`: when something does not work.
- `themes/ink-study`, `themes/deep-orbit`, `themes/defrag-95`: complete examples of fusion in three very different worlds.
