# Reviewing a theme before the user sees it

Users judge a desktop in one glance. A theme that is clever but looks cheap has failed, and "cheap"
is almost always the same handful of faults: a system fallback font, flat fills, hard outlines, too
many sizes and colours, choppy or mechanical motion, banding in dark gradients, and a browser bubble
popping up on top. The agent is the art director here. Nothing is "done" until it has been looked at,
in every size and state, and every item below has an honest answer.

## The loop

1. **Run the review.** `orbit.py review <id>` renders the theme at 1920×1080, 1366×768, 2560×1440,
   3440×1440 and 1280×1024, in day, night with rain and English, plus any states the theme lists in
   theme.json (`"review": {"states": {"praying": "pray=…"}}`: query strings your scene.js understands).
   The page also measures itself (fonts, fallbacks, overlaps, tiny text, icon and taskbar zones,
   script errors, network requests). Everything lands in `~/OrbitDesktop/review/<id>-<time>/`.
2. **Look at every picture.** Open each PNG and answer the checklist below item by item, writing down
   what you see, not what you intended. Zoom into the details: text edges, the brightest and darkest
   areas, anything small.
3. **Fix and repeat** until the automatic findings are clean and every checklist answer is "yes".
4. **Check the real desktop after installing.** Ask the user, then `orbit.py capture` and look at the
   picture: the theme behind real icons and the taskbar, at the real resolution and scaling. If you can
   drive the mouse (computer use), hover and click the controls and capture again; if a function opens
   a window, open it and capture that too. Watch for anything the host adds: a translate bar, a
   "press F11" bubble, a permission prompt, a focus that lands in the wrong place.
5. **Then show the user**, with the pictures, and say what you checked.

## The checklist

**Typography**
- [ ] Every text is in the intended font: no fallback (the review lists any). Fonts are bundled in the
      theme (`orbit.py fonts`), not loaded from the network at run time.
- [ ] At most two families (one display voice, one text face) and a short scale: display, title,
      text, caption. Sizes come from that scale, not ad hoc.
- [ ] Tracking is deliberate: wide letter-spacing only on short labels and capitals; Chinese body text
      at 0–0.2em. Nothing looks like a slide template.
- [ ] Nothing is under 11px at 1366×768; light weights are not used below ~16px (they shimmer on Windows).
- [ ] Numbers that change (clocks, counters) use tabular figures and do not jitter.

**Light, material and colour**
- [ ] One focal point, clearly the brightest and sharpest thing on screen.
- [ ] No large flat fills: big areas carry a gradient, texture or light falloff.
- [ ] Depth: far things are softer and hazier, near out-of-focus things are blurred, the focal subject
      is crisp. No hard outlines around shapes that should read as silhouettes (use rim light).
- [ ] Glows are soft (pre-blurred sprites or layers), never a hard ring or a visible square edge.
- [ ] Dark gradients do not band (add the film grain overlay or noise).
- [ ] Four to six colours from the world's materials; accents used sparingly; day and night both look intended.

**Motion**
- [ ] Continuous motion runs at 60 fps (`Orbit.loop(draw, { fps: 60 })`) on soft pre-rendered layers;
      it pauses when hidden.
- [ ] Ambient motion is slow and organic (noise fields, long cycles); nothing jitters, strobes or
      moves linearly from a standing start.
- [ ] Event motion (a function running) reads as the world's own event, item by item, with easing.
- [ ] `prefers-reduced-motion` is respected.

**Composition and layout**
- [ ] The icon side of the screen and the taskbar zone are calm; the review reports no text there.
- [ ] Nothing overlaps or leaves the screen at any of the reviewed sizes, including 3440×1440 and 1280×1024.
- [ ] Controls sit in one cluster near where the eye rests, aligned to each other; margins are consistent.
- [ ] At least a third of the screen is quiet.

**Interaction**
- [ ] Every clickable thing reacts to hover, and to a click, in the world's language.
- [ ] Something in the scene responds to the cursor (light, particles, parallax), subtly.
- [ ] Confirm, running, done, error, empty, undo and offline states each look designed (snapshot them).
- [ ] Typing never happens on the wallpaper itself: wallpaper hosts pass clicks, not the keyboard or an
      input method. A theme that takes text opens its own window (see theme-guide.md).

**Host and robustness**
- [ ] No browser UI appears: `<html translate="no">` (the SDK sets it) and windows opened by the
      theme use a quiet profile (`hosts.quiet_profile`): no translate bubble, no first-run pages.
- [ ] Works offline: the review shows no network requests except weather through the helper.
- [ ] No script errors; the theme recovers when the helper restarts (offline state, then back).
- [ ] Idle cost is acceptable on the user's machine (Task Manager / Activity Monitor: the wallpaper
      process stays low while nothing happens).
