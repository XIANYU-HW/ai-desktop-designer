# Reviewing a desktop theme

Acceptance checks whether the result fulfills the brief and works in the intended environment. A
screenshot, automated report and real host test answer different parts. Record observations, evidence
paths and environment details. Use pass, needs repair, unverified, or not applicable with a reason.
Never turn missing evidence into a pass.

## The review loop

1. **Set scope.** Map requested functions and visual requirements to checks. Note theme/version,
   host/browser, OS, display size/scale, language and the original installation to preserve.
2. **Build repeatable cases.** Use `?demo=1` and fixture queries. Declare applicable cases in
   `theme.json` under `review.states`, implement each query, and verify the intended state appeared.
   A query name alone creates nothing. Fixtures must never run real actions. See theme-guide.md.
3. **Run automatic checks.** `orbit.py validate <id>` then `orbit.py review <id>`. Inspect coverage,
   measurements, failures and image paths, not only the exit code. `--quick` is an iteration aid with
   a reduced matrix; its report does not establish full acceptance.
4. **Inspect actual images.** Open every image used for acceptance at overall and detail scales.
   Compare direction, hierarchy and requested features with the brief across target sizes and relevant
   state/language combinations. Fix defects and re-render affected cases.
5. **Exercise a running preview.** In demo mode test hover, focus, clicking, cancellation, repeated
   activation and full transitions. Watch motion and pause/resume. Test custom action behavior on
   isolated data separately and read back the resulting state. Simulated success proves presentation only.
6. **Verify the actual host when available.** Within authorized scope and permitted UI tools, inspect
   the desktop and companion windows: icons, taskbar/Dock, scaling, input, focus, translation prompts,
   reconnect and motion pause. Do not switch the host/startup settings merely to collect evidence.
   If Windows, Plash or the native Mac app is unavailable, identify that environment as unverified.
7. **Deliver evidence.** Give requirement coverage, representative final images, changes, recovery and
   limitations. Separate automatic checks, visual inspection, action behavior and host verification.
   Unavailable checks need not prevent showing useful work, but prevent claiming that capability passed.

Page measurements are heuristics for DOM text, selected controls, fonts, resources and script errors.
They do not fully inspect canvas/SVG content, prove glyph coverage/contrast, measure motion quality,
inspect browser chrome or establish that an OS effect succeeded. Static review disables transitions
for capture. Use visual and running checks for these gaps.

## Reproducible interaction cases

For applicable features record trigger, fixture/input, expected result, observation and evidence.
Absent features can be marked not applicable.

| Feature | Cases to cover |
|---|---|
| Action control | Idle, hover/focus, preview/armed, cancel, running, done, failure, empty, unavailable, undo/recovery |
| Lists/counts | Zero, one, maximum/overflow, long names, partial success and skipped items |
| Data | Populated, missing, stale/offline, reconnect; distinguish samples from actual readings |
| Text/AI entry | Empty/long text, Chinese composition, selection/paste, submit/cancel, blur/return, reopen with draft, handoff failure and confirmed destination state |
| Motion | Idle/event cycle, repeated/large events, reduced motion, hidden/resume, resource use |
| Host window | First/repeat launch, focus/return, unintended browser prompts, close behavior |

Save fixtures as deterministic data or queries. Reuse live rendering functions where possible, freeze
a meaningful point for a still, then test the transition separately. Include canceled and failed
operations. Never click a live file/app/system action just to see its animation without authorization.

## The checklist

Write an observation and evidence path for each applicable item, or a concrete unverified/not-applicable
reason. This is a review record, not an automatic aesthetic score or a prescribed style.

**Requirements and scope**
- [ ] Every requested feature and preservation constraint maps to behavior and a check.
- [ ] The result follows the chosen direction; no function was omitted for lack of a metaphor.
- [ ] A recoverable prior version/config is identified; existing native Mac ORBIT remains intact
      unless changing it was explicitly requested.

**Typography and composition**
- [ ] Actual fonts, glyphs, readable size/contrast, spacing and numeric stability match the direction
      on the tested platform; intentional system or pixel fonts are acceptable.
- [ ] Hierarchy, alignment, margins and usable space fit the user's desktop.
- [ ] Detail inspection found no accidental seams, placeholder art, clipped effects or rough edges.
- [ ] Target screen shapes, long labels and populated states fit without accidental overlap/clipping.

**Motion and resources**
- [ ] Moving content was watched in a running preview; timing and feedback match the direction.
      Static themes are intentionally static.
- [ ] Pause/resume, reduced motion and repeated effects work where tested; resource use is measured
      on the stated machine or left unverified.
- [ ] Implemented frame cap, rendering scale and bounded effects fit the budget; nominal fps alone
      was not used as evidence of smoothness.

**Interaction and results**
- [ ] Applicable fixtures actually rendered; triggers and outcomes are recorded, including error,
      empty, cancel, partial and recovery paths.
- [ ] Controls explain their effect/scope and show hover/focus/disabled/running states; live feedback
      reflects actual results and simulated feedback is identified.
- [ ] Text preserves drafts across focus changes and failed handoff; language/IME behavior was tested
      when input is present. AI send/receive claims have separate evidence.
- [ ] Custom actions were checked on disposable data and resulting state read back; simulated success
      was not counted as a real operation.

**Host and evidence**
- [ ] Expected cases, images and measurements reconcile. Missing evidence is flagged; findings were
      repaired or explained as intentional with supporting inspection.
- [ ] Offline assets and helper recovery were checked for the promised use; unavailable data is clear.
- [ ] Available real hosts and companion windows were checked for scaling, desktop obstacles,
      keyboard/IME, focus and translation/full-screen prompts. Browser-only evidence is labeled.
- [ ] Delivery identifies automatic, visual, action and per-host results, remaining limitations and
      how to restore the prior configuration.
