# Contrasting design and acceptance cases

These are examples, not presets or mandatory layouts. Keep the user's functions and requirements.
None proves the runtime already supplies the custom behavior.

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
