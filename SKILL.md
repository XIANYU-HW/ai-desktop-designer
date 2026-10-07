---
name: orbit-desktop
description: Create or customize an integrated desktop experience on Windows or macOS, combining wallpaper, visual style, motion, widgets, and existing or newly built desktop actions. Use for desktop design, theme changes, custom desktop functions, or Orbit setup and repair. Not for editing a single standalone image.
---

# Orbit Desktop

Build the desktop the user asked for. Its imagery, typography, motion, information and controls should
form a coherent design. Any style is valid: quiet typography, photography, illustration, pixel art,
a fictional setting or a practical workspace. The examples are starting points; their layouts,
functions and metaphors are optional.

The portable implementation is a web theme, a local Python 3.9+ helper (`runtime/orbit.py`, standard
library only), and independent actions. Lively Wallpaper is the Windows host; Plash is the macOS host.
A browser is a preview or companion window. These are distinct environments needing separate checks.
An existing native Mac ORBIT app is reference material, not this runtime: preserve its app, themes,
settings, login items and current desktop unless the user explicitly requests a change to them.

## Scope and recoverability

- Use existing authorization. Designing a control does not authorize executing its real effect.
  Develop with demo mode, read-only operations or isolated test data. The CLI requires `--yes` for
  effects `files`, `apps` and `system`; this flag is not user authorization by itself.
- Use a new theme ID or preserve a recoverable copy before editing an existing theme. Record the
  current active theme and relevant configuration before applying changes. Keep unrelated files intact.
- Install software, change the desktop host or enable startup only within the requested scope.
  `install` does not enable helper startup by default; `install --autostart` or `autostart on` requires
  that choice to be authorized. Previewing does not require installation.
- Custom actions may implement behavior beyond the built-ins. Describe the effect and scope, provide
  a preview when meaningful, and design appropriate recovery. Read [action-guide.md](references/action-guide.md).
  A manifest does not give custom scripts the built-ins' guarantees. Preserve the built-ins' protections
  against deletion and forced app closure.
- Imported themes and actions are executable code; review them before running. External sends,
  publication and account access need corresponding authorization; installing a theme grants none.

## Choose the work needed

**New design or substantial redesign.** Read [design-principles.md](references/design-principles.md).
Capture requested functions, visual direction, language, target screens/hosts, motion preference and
constraints in a short brief. Use context and sensible defaults; ask only for choices that materially
change the result. Track each requirement to implementation and verification. Keep requested functions
even when they need plainly labeled controls rather than metaphors.

**Theme change.** Inspect the existing theme and preserve what the user wants. Read
[theme-guide.md](references/theme-guide.md) for the manifest, SDK and safe review fixtures. Build with
`new-theme <id> --from template` or copy an appropriate example into `~/OrbitDesktop/themes/<id>/`.
The template is a replaceable static skeleton, not an approved design or prescribed widget list.
Use supplied/generated artwork, CSS, SVG, canvas, video or shaders when suitable for the design and
host. Verify assets and fonts instead of substituting generic shapes automatically.

**New or changed function.** Check [builtin-actions.md](references/builtin-actions.md) for reusable
parameters; otherwise use `new-action <id>` and [action-guide.md](references/action-guide.md). Connect
real status, progress and results to the design. Test on disposable data before authorized real use.
An AI prompt field or bridge is not a shipped built-in: implement and verify the requested integration,
preserve drafts, and distinguish opening a draft, sending it and receiving a result.

**Preview and acceptance.** Read [quality-review.md](references/quality-review.md). Run `validate` and
`review`, inspect actual images, exercise applicable interaction states, and watch moving content in
a running preview. Repair defects and recheck affected cases. Automatic findings, visual review and
real host verification are separate evidence. A clean report never certifies artistic quality,
working actions, smooth motion or Windows/macOS behavior by itself. Report unavailable checks honestly.

**Apply to the desktop.** After the preview meets the brief, follow [hosts.md](references/hosts.md).
When available and authorized, check the real desktop at its actual resolution, scale, icon/Dock/taskbar
arrangement and input behavior. Use permitted screen inspection tools; `capture` is an optional local
screenshot command. Keep a recovery route and distinguish an applied host setting from verified
rendering. Do not replace the native Mac installation by default.

**Repair only.** Use `doctor` and [troubleshooting.md](references/troubleshooting.md), reproduce the
reported problem, and change the responsible part. A translation prompt needs an actual window check;
adding `translate="no"` or a browser flag alone does not prove it is gone.

## Runtime essentials

`SKILL_DIR` is the folder containing this file. Use the available interpreter:

```text
python  "<SKILL_DIR>/runtime/orbit.py" <command>     # Windows; py -3 also works
python3 "<SKILL_DIR>/runtime/orbit.py" <command>     # macOS / Linux
```

User data is in `~/OrbitDesktop` (`config.json`, `themes/`, `actions/`, `state/`, `logs/`). Workspace
items override bundled items with the same ID. Inspect before initializing or changing existing config.
For a new workspace: `doctor`, `init --lang zh-CN` (or `en`), then `start` when a preview needs it.
Set weather location only when requested or known; resolve ambiguous city matches instead of silently
selecting the first result. Linux can preview the theme; the desktop targets are Windows and macOS.

| Task | Commands |
|---|---|
| Inspect | `doctor`, `status`, `themes`, `actions`, `config` |
| Workspace/helper | `init [--lang zh-CN\|en]`, `start`, `stop` |
| Author | `new-theme ID [--from template\|THEME]`, `new-action ID` |
| Check | `validate ID`, `validate-action ID`, `run ACTION preview --param KEY=VALUE` |
| Render | `snapshot ID [--size WxH] [--query Q]`, `review ID [--quick]` |
| Running preview | `open ID --window`; helper-served pages can run real actions, so use `?demo=1` for safe interaction tests |
| Bundle fonts | `fonts ID --family F [--weights 400,600] [--chars common-zh] [--script latin\|cjk]` |
| Apply/recover | `use ID`, `install [--autostart]`, `uninstall`, `autostart on\|off\|status` |
| Optional real-screen evidence | `capture [--out F] [--delay S]` within authorized scope |
| Transfer | `export-theme ID`, `import-theme ZIP` after reviewing the source |

`snapshot` and `review` use demo data by default. Read their reports for actual coverage; `--quick` is
an iteration aid, not full acceptance. Prefer repeated `--param` arguments for cross-platform shells.
The SDK and helper do not supply an AI model or automatically send prompts to another application.

## Design and evidence references

- [design-principles.md](references/design-principles.md): direction, craft, functions, motion and resources.
- [theme-guide.md](references/theme-guide.md): implementation, SDK, fonts, input windows and fixtures.
- [quality-review.md](references/quality-review.md): repeatable acceptance and evidence requirements.
- [design-cases.md](references/design-cases.md): contrasting examples for choosing a design and review plan.
