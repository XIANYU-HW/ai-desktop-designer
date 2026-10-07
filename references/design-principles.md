# Designing an integrated desktop

The user's experience determines the design. A coherent result may be restrained and flat, richly
illustrated, photographic, nostalgic or cinematic. Craft means executing that direction well; there
is no required focal light, card shape, font category, metaphor, particle system or frame rate.

## Brief and requirement trace

Before a substantial build, record requested functions, information, references, language, target
host/screens, motion preference and things to preserve. Reuse choices already made. A short note is
enough for a small edit. Theme `concept` describes the direction; optional `requirements` can track
implementation. These are authoring notes, not runtime controls or automatic validation.

| Requirement | Implementation | Evidence needed |
|---|---|---|
| Visual direction | Assets, type, palette, composition | Actual rendered overview and detail inspection |
| Widget or action | Visible control + data/action binding | State fixture, behavior test and result readback |
| Target screen and host | Responsive layout + host interaction | Render at size/scale; actual host when available |
| Preservation/recovery | Independent ID or recoverable copy | Original path/version and restore route |

Keep every requested requirement or identify what remains unresolved. Do not drop a function to make
a metaphor table cleaner. Optional ideas must not displace required work. New functions are allowed;
the supplied file and app actions are examples, not the definition of the product.

## Art direction and composition

Choose how imagery, type, controls and motion relate. A literal tool label can fit a setting through
material, placement and typography; a fictional name helps only when the real effect remains clear.
For example, “收卷” can include “整理桌面文件” in its subtitle or preview. Progress can become a scene
event when useful, but actual completion must come from the action result.

Use references to identify framing, value structure, color balance, texture, type proportions and
motion. Select a production method that can deliver them. Supplied or generated artwork, vectors,
photos, video, CSS and procedural rendering are all valid. If image-generation tools are available
and appropriate, use their workflow. Do not approximate detailed art with a few geometric shapes merely
because that is easy to code.

Compose for the actual desktop. Icons and the Dock/taskbar have configurable positions and sizes;
their arrangement is not guaranteed by the OS name. Establish hierarchy and readable controls at normal
viewing distance. Controls may be clustered, split into purposeful zones or integrated with the artwork.
Test the smallest and widest target sizes, long labels, populated lists and unavailable data.

## Typography and material

- Choose a deliberate type system and consistent scale. System fonts can be correct; unintended
  fallback is the defect. Bundle licensed display fonts when portability matters and inspect actual
  Chinese, Latin, numbers, punctuation and user-entered text on target systems.
- Use contrast, spacing, alignment and reading sizes suitable for screen scale and viewing distance.
  Tiny light text that looks good enlarged may fail on Windows or a dense laptop screen. Treat automatic
  size warnings as prompts to inspect, not universal design laws.
- Use color/material tokens suited to the direction and distinguish interaction, warning and error
  states. Flat fills and hard edges are valid in flat or pixel styles. Depth, texture, rim light, grain
  and bloom belong only where the artwork calls for them.
- Inspect the composition and then details: rough silhouettes, weak asset integration, accidental seams,
  unreadable labels, excessive spacing, mismatched fonts and default-looking controls. Adding grain or
  glow does not repair weak drawing, composition or typography.

## Motion and performance

Choose a budget for the target hardware and host: rendering size/pixel ratio, continuous frame rate
if any, maximum active effects, and acceptable measured idle CPU/GPU use. Record its basis. Manifest
`performance` values are descriptive until code uses them. Static themes should not run a drawing loop.
For moving themes, select the rate by observed smoothness and power cost; 24, 30 or 60 fps can each fit.
A requested frame cap is not a measured rate.

Separate rendering into layers:

- **Base imagery:** static or cached expensive painting, layout and blur work.
- **Ambient motion:** requested subtle movement, paused when hidden; limit changing pixel area.
- **Interaction/action feedback:** bounded effects tied to pointer activity or real action events.
- **Controls and text:** clarity, stable hit targets and input focus throughout transitions.

Choose curves, physical models, noise or deliberate stepping according to the scene. Orbits may be
periodic; pixel animation may step; a calm workspace may be still. Avoid unintended jitter, flashes,
jumps on resume and success effects before confirmed results. Bound particles and queued work so large
file counts cannot cause excessive animation.

`Orbit.loop` handles SDK pause signals and a reduced frame rate. It does not prove every host sends
those signals or that reduced motion is satisfactory: 2 fps may feel worse than no animation. Design
a still/low-motion variant, handle preference changes when needed, and pause CSS, video and custom
loops too. Verify hide/resume and reduced motion in the running host. Measure before promising a CPU
percentage or smoothness.

## Functions and input

Use real status/progress when connected and identified fixtures during review. Handle zero, one and
many items, long names, missing or stale data, offline state, partial completion and errors without
inventing success. Show effect, scope and recovery when needed. Avoid confirmations for harmless visual
interaction; keep consequential actions within their authorization and operation contract.

Choose a host-appropriate input surface. A companion window can be more usable than a full-screen
duplicate. Preserve drafts on blur, app switching, failed handoff and reopening according to privacy
requirements. AI entry needs a separately implemented integration; opening a draft, sending it and
receiving a reply are distinct states. See theme-guide.md.

Use [quality-review.md](quality-review.md) to compare the implementation with the brief. Repair
demonstrated defects, preserve intentional style choices, and report unavailable checks as unverified.
See [design-cases.md](design-cases.md) for contrasting examples.
