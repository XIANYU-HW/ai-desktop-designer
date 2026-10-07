# Troubleshooting

Start with `orbit.py doctor`; the helper's log is `~/OrbitDesktop/logs/orbit.log` and action output is
logged there too.

| Symptom | Cause and fix |
|---|---|
| `python` is not found, or opens the Microsoft Store | Install Python 3.9+ (`winget install -e --id Python.Python.3.12 --scope user`) or use `py -3`. Turn off the Store "app execution alias" for python if it keeps opening the Store. |
| The desktop shows "can't reach this page" | The helper is not running: `orbit.py start`, then reload the wallpaper (Lively tray icon → reload, or `Lively.exe setwp --file reload`). `orbit.py autostart status` should say on. |
| `Port 47321 is busy` | Another program uses the port. `orbit.py config port 47400`, `orbit.py stop`, `orbit.py start`, then `orbit.py install` again so the wallpaper points to the new port. |
| Buttons on the desktop do nothing | Windows: Lively's mouse input must be on and the click must not land on an icon. Lively passes clicks only while the desktop has the focus: coming from another window, the first click just focuses the desktop and the second one reaches the theme (hover always works). macOS: turn on Plash's Browsing Mode. The page also shows "helper offline" when the helper is down. |
| A "Translate this page?" bubble appears | It comes from a browser window the theme opened. Pages get `translate="no"` from the SDK; windows opened by actions must use `hosts.quiet_profile()` and `hosts.browser_window_args()` (translation off, the user's language as the browser language). |
| Typing on the desktop does nothing, or Chinese input does not work | Wallpaper hosts never pass the keyboard or an input method to the page. Take text in a window of its own (theme-guide.md, "Text input"). |
| `401 token-required` in the browser console | The page was opened from a file or another address. Open it through `http://127.0.0.1:<port>/`. |
| Weather is empty | `orbit.py set-location "<city>"`. Behind a proxy, Python uses the system proxy settings; check that Open-Meteo is reachable. |
| Text falls back to a plain font | The theme's font is not installed or a web font could not load offline. Add a system-font fallback stack. |
| High CPU or fan noise | Lower `fps` in `Orbit.loop`, pre-render static layers, cap devicePixelRatio at 2, remove per-frame blur. |
| Tidy skipped some files | They are open in another program, were changed in the last 30 s, are shortcuts or hidden files, or folders. `orbit.py run tidy-files preview` lists each reason. |
| An app did not close | It is showing a "save changes?" dialog (status `waiting`), it runs as administrator (`skipped`), or it is on the protected list. Nothing is ever force-quit. |
| Windows SmartScreen warns about `start-windows.bat` | Files from a downloaded ZIP carry a web mark. Choose "More info → Run anyway", or clone the repository with git instead. |
| `--params must be JSON` in Windows PowerShell | PowerShell 5.1 removes the quotes inside JSON arguments. Use `--param key=value` (repeatable) instead, e.g. `--param source=downloads`. |
| Lively shows Orbit Desktop twice | The Store version was given the address by hand although the entry already existed. Delete one of them in Lively's library. |
| Snapshot fails | Install Chrome or Edge, or point `ORBIT_BROWSER` to a Chromium-based browser executable. |

## macOS CI browser startup

CI uses the supported `macos-15` ARM64 runner label and pins Chrome for Testing to
155.0.8059.39. The setup action's exact-version installer preserves the outer
`.app` bundle; its `stable` channel installer copies the bundle contents into its
cache root instead. These explicit choices make the OS generation, browser
version and package layout reproducible. The complete macOS test and browser
screenshot checks still run. Available labels are listed in the
[official runner images table](https://github.com/actions/runner-images#available-images).

On 2026-10-07, runner image `macos-26-arm64/20260907.0351` (macOS 26.6.2) with
Chrome for Testing 155.0.8059.39 installed using the `stable` channel layout failed
before rendering a minimal HTML page:
child processes logged `MachPortRendezvousServer` / `Permission denied (1100)`,
then repeatedly terminated without a rendezvous client. Both `data:` and local
HTTP pages failed with a new session or a new process group; each attempt reached
its 20-second limit with no screenshot. This isolates that observed failure to
browser startup in that CI environment, but does not establish its underlying
OS/browser/package-layout cause or imply that every macOS 26 installation is
affected. A successful run in the pinned environment does not by itself identify
which of those differences resolved the failure. See the
[diagnostic run and full stderr artifacts](https://github.com/XIANYU-HW/ai-desktop-designer/actions/runs/37582760338).

For a similar failure, retain the browser version and complete startup stderr,
and try a minimal page before investigating theme code. The failure-only CI
diagnostic step records these details with bounded cleanup of its own browser
process groups. Keep browser sandboxing enabled.
