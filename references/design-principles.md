# Designing a desktop where function and beauty are one

Most desktop customizers stop at the picture. Widgets and tools are then dropped on top of it as
generic cards, and the result looks bolted together. An Orbit theme is designed the other way round:
pick one world, then let every function, number and state become part of that world.

## 1. Start from a world, not from a widget list

Choose one concrete world: a place, an era, a craft, an instrument, a story. Good worlds have their own
materials, light, vocabulary and ways of moving.

| World | Materials | Vocabulary | Motion |
|---|---|---|---|
| A scholar's study in misty mountains | xuan paper, ink, a seal, an oil lamp | 收卷, 书阁, 时辰 | mist drifting, ink blooming |
| Mission control above a planet | thin lines, monospace, glass panels | capture, telemetry, silent running | orbits, captures, lights going dark |
| Windows 95 | bevelled grey, teal, pixels | Defragment, End Task, Resource Meter | blocks read and written, progress bars |

Write the world down in theme.json `concept` before writing any code: `world`, `mood`, `type`, `motion`.

## 2. Translate every function into the world

Make a metaphor table (`concept.metaphors`) with one row per function and per piece of data. A good row:

- **Maps the real effect to a believable event in the world.** Filing desktop files is "rolling up loose
  pages into a scroll", "capturing debris into orbit", "defragmenting". Never a generic "Clean" button with a broom icon.
- **Names it with the world's verb**, short. Keep the plain meaning findable: a small subtitle, the
  status line, or the confirm message say what will really happen ("将收纳 8 个文件").
- **Turns real data into world state.** Counts become objects (8 loose files = 8 specks of debris, 5 open
  apps = 5 lit satellites); levels become quantities (battery = lamp oil); time and weather become the
  world's own (the double-hour 申时, rain falling as ink strokes).
- **Shows progress as the world's own motion, item by item, driven by real progress events.**
  `Orbit.on('action', e => ...)` with `e.phase === 'progress'` fires once per moved file or closed app.
- **Shows risk in the world's warning language.** Closing apps arms first (a warm lamp glow, an amber
  blinking key, a dialog that lists the programs), then a second click confirms.
- **Has a way back.** Undo exists in the world too: unroll, release, scatter back, relight.

If a function has no natural place in the world, the world is probably wrong for it; either pick a
richer world or leave the function out of this theme.

## 3. Compose for a real desktop

- **Desktop icons.** Windows puts icons in columns from the top-left, macOS from the top-right. Keep
  that side calm: use the `--safe-left` / `--safe-right` pattern from the examples (set from `data-os`).
- **The taskbar or Dock** covers the bottom or a side. Keep controls above the bottom ~6% of the screen.
- **Any screen.** Lay out with `vh`, `vw` and clamp(); test 1366×768, 1920×1080, 2560×1440, ultrawide and
  4:3. Text at least about 11 px on a 1080p screen. Never let panels overlap at any of these sizes.
- **Negative space.** Leave at least a third of the screen quiet. Put controls in one cluster, near
  where the eye rests (often bottom-right on Windows), not scattered over the scene.
- **One focal point** in the scene (a sun, a planet, a window), with everything else supporting it.

## 4. Type, color and light

- One display voice from the world (KaiTi, a monospace, MS Sans Serif) and at most one text face.
  If the voice is a web font, **bundle it in the theme** with `orbit.py fonts` (subsets from Google
  Fonts saved under assets/fonts, so the desktop looks the same offline and where Google is blocked).
  A theme that silently falls back to SimSun or Times New Roman looks cheap however good the art is.
  Always end the stack with a fallback that still looks decent (Windows: Microsoft YaHei UI; macOS:
  PingFang SC), not SimSun.
- Keep a short type scale (display, title, text, caption) and use it everywhere. Wide letter-spacing is for
  short labels and capitals only; Chinese text reads best at 0–0.2em.
- Four to six color tokens drawn from the world's materials, one accent, and separate semantic colors
  for warning and error. Define them as CSS custom properties on `:root`.
- Use the time of day: the SDK sets `data-daypart` (dawn, day, dusk, night) and `data-weather`
  (clear, partly, cloudy, fog, drizzle, rain, snow, storm) on `<html>`. A desktop that dims at night and
  rains when it rains feels alive; redefine the tokens per daypart instead of using a separate dark theme.

## 5. Motion

- Ambient motion is slow: cycles of 20 seconds or more, small amplitudes, nothing that pulls the eye
  while the user works. Event motion is quick but readable: 0.6 to 1.6 s per item.
- Never flash or strobe. Respect `prefers-reduced-motion` (`Orbit.loop` drops to 2 fps automatically;
  CSS animations need a media query).
- Animate with `Orbit.loop(draw, {fps})` so the scene pauses when the wallpaper is hidden or covered by a
  full-screen app. Anything that moves continuously (particles, smoke, turning rings, parallax) runs at
  60 fps: at 30 fps slow motion visibly steps, and stepping reads as cheap. Pay for it by pre-rendering
  (section 7), not by dropping frames. 30 fps is fine for scenes that change in discrete steps.
- Drive organic motion with smooth noise (simplex/value noise fields), not stacked sine waves: dust that
  drifts on a flow field looks like dust; dust on `sin(t)` looks like a screensaver.

## 5½. Craft: what separates premium from cheap

The same idea can look like a film still or like a slide template. The difference is craft:

| Looks cheap | Looks made |
|---|---|
| Fallback system fonts, five sizes, letter-spacing everywhere | Bundled fonts, a four-step scale, tracking only on labels |
| Large flat fills and hard-edged shapes | Light falloff, texture, gradients that follow a light source |
| Everything equally sharp | Depth: far things soft and hazy, foreground out of focus, the focal subject crisp |
| Outlines around figures and objects | Rim light on the edge that faces the light; silhouettes melt into the dark away from it |
| Hard glow rings, glows clipped to squares | Soft bloom from pre-blurred layers or sprites |
| Banding in dark gradients | A fine animated film grain over everything (CSS overlay, `mix-blend-mode: overlay`) |
| Particles as dots or squares in random jitter | Dust with depth (tiny sharp far, a few large soft bokeh near) on a flow field |
| A light "beam" as a flat trapezoid | A soft volumetric column with drifting smoke that only shows where it is lit |
| Many elements competing | One focal light, a third of the screen quiet, everything else supporting |
| UI popping up abruptly | An entrance (the scene fades up), eased transitions, nothing appearing in one frame |
| Browser chrome or a translate bubble on top | No browser UI ever (translate="no", quiet browser profiles) |

Build in layers: paint the static, soft things once (blurred by depth with `ctx.filter = 'blur()'` at build
time, often at half resolution), then each frame only composite them and draw the few crisp, moving
lines live. That is what makes 60 fps affordable.

## 6. Design every state

| State | Where it shows | Example |
|---|---|---|
| Offline (helper not running) | `data-orbit-connection="offline"` on `<html>` | dim the controls, say "helper offline" |
| Nothing to do | action status, `is-unavailable` | 收卷 shows "案头已净" and dims |
| Running | `is-running` on the button, progress events | slips fly, blocks move |
| Done / error | `is-done` / `is-error` for ~2.6 s, status message | ink bloom, red border |
| Asking to confirm | `is-armed`, `confirm` event with the preview | lamp glows; list of apps |
| Undo available | `is-unavailable` removed from the undo button | 展卷 appears |

## 7. Performance budget

A wallpaper runs all day. Aim for under 3% CPU when idle on a laptop.

- Paint static layers once into an offscreen canvas and redraw them only on resize or daypart change.
- Cap the canvas pixel ratio at 2. Avoid per-frame blur filters, huge shadows and thousands of particles.
- Keep the theme folder under 40 MB; prefer procedural art (canvas, SVG, CSS) to large videos.

## 8. Avoid

- Generic dashboard cards with stock icons, glassmorphism everywhere, gradients that mean nothing.
- Widgets for their own sake. Show only data that the world can carry.
- Emoji as icons. Draw icons in the world's style (a seal, a key cap, a 16-pixel bitmap).
- Copying a brand's or a franchise's look into a theme you share publicly.

## Checklist before showing the user

- [ ] `concept` in theme.json names the world and maps every function and every piece of data.
- [ ] Each control has a world name and its real meaning is findable.
- [ ] Progress, confirm, done, error, empty and offline states are all designed.
- [ ] `orbit.py validate` reports no errors.
- [ ] `orbit.py review <id>` is clean, and you have opened every picture it made and answered every item in
      `references/quality-review.md` with what you saw.
- [ ] After installing, `orbit.py capture` (with the user's OK) shows the theme right on the real desktop.
