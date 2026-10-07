# Contrasting design and acceptance cases

These are examples, not presets or mandatory layouts. Keep the user's functions and requirements.
The hypothetical cases below do not imply that the runtime supplies their custom behavior.

## Implemented showcase cases

Read the source and inspect a running demo before reusing a technique. These two themes demonstrate
different compositions; neither is a mandatory house style. Artwork provenance is in
[showcase-art.md](../docs/showcase-art.md), and actual checks in
[showcase-verification.md](../docs/showcase-verification.md).

| Theme | Core idea → design → behavior | Useful function and limits |
|---|---|---|
| [Three-body Observatory](../themes/threebody-observatory/) | Unpredictability and civilization records → dark bronze instrument and quiet left-hand text → compare reference and perturbed finite trajectories, pointer observation, freeze | A 25-minute deadline-based focus timer; clearly labeled file/library/quit tools. The equal-mass softened model is conceptual, not a prediction of fictional or real planetary eras. |
| [Sumeru Garden](../themes/genshin-sumeru/) | Knowledge and growth → tree city, illuminated scrolls, distributed botanical controls → image-aligned water glints, bounded blooms and branching elemental responses | Browser-local notes with draft recovery; the same file/library/quit tools in a different material language. Reactions interpret a theme, not game combat rules. |

The connection must be visible in the scene and usable in the control. Naming a generic button after
an IP character is insufficient; adding ornament must not conceal what the action does. For lavish
art, keep quiet regions around text, animate selected materials rather than warping the whole image,
and inspect both the normal state and the most elaborate interaction state at the target resolution.

## Further design briefs

| Request | Design choices | Evidence that matters |
|---|---|---|
| Monochrome work desktop with clock, project folders and a focus timer | Flat background, deliberate system type, labeled controls, no ambient loop, restrained timer completion | Readability/size; folder action; timer start/pause/cancel/finish on disposable state; restart recovery; idle resource use |
| Pixel observatory with weather and music controls | Crisp pixels, limited palette, intentional stepped motion; readable period font; custom music action | Pixel alignment at scale; glyph coverage; missing player and playing/paused/error states; authorized player readback; host input/focus |
| Illustrated rain library with filing and AI writing entry | Quality artwork with local rain layers; integrated type; clearly explained filing scope; draft-preserving companion input if needed | Overview/detail review; motion/reduced mode; filing/undo on disposable files; Chinese IME and draft recovery; real-window translation check; separate AI draft/send/result evidence |

Example requirement trace for the rain library:

| ID | Requirement | Implementation | Acceptance |
|---|---|---|---|
| R1 | Rain supports reading | Local rain layer and reduced-motion still | Full cycle, pause/resume, still/animated composition |
| R2 | Filing can be reversed | Tidy action with requested parameters | Disposable zero/one/many files; moved/skipped/error and undo readback |
| R3 | AI text survives app switching | Companion input and draft storage with explicit clear control | Chinese/long text; blur/return; close/reopen; handoff failure; compare draft |
| R4 | Preserve current Mac desktop | New workspace theme and preview until applying is authorized | Prior app/config unchanged; preview path recorded; Plash remains unverified if not applied |

Fixtures might include `empty`, `many`, `armed`, `cancelled`, `running`, `partial`, `error`, `undo`,
`offline`, `typing` and `handoff-error`. Declare only implemented states. Capture relevant size/language
combinations and exercise transitions in demo mode. Still images cannot prove the timer, player, file
effect or AI integration works; test behavior separately without unauthorized effects on user data.
