# Built-in actions

Operations marked *read* never change anything and are safe to call while designing. Parameters can be
set per user in `~/OrbitDesktop/config.json`:

```json
{ "actions": { "quit-apps": { "params": { "keep": ["WeChat", "spotify.exe"] } },
               "tidy-files": { "params": { "library": "{documents}/Desktop Archive" } } } }
```

and per button in a theme with `data-orbit-params='{"source":"downloads"}'` (a theme can only set
parameters the action declares). Test any operation from the command line:
`orbit.py run <action> <op> [--params '{...}'] [--yes]`.

## tidy-files · 一键收纳 (Windows, macOS, Linux)

Moves loose files from a folder (the desktop by default; Windows' OneDrive-redirected desktop is
handled) into category folders. Every run is journaled and can be undone.

| Op | Effect | What it does | Data |
|---|---|---|---|
| `status` | read | Counts loose items, checks undo | `pending`, `kept`, `source`, `library`, `last_run`, `available` |
| `preview` | read | Lists what would move where | `pending`, `by_category`, `items[]` |
| `run` | files | Moves them; progress per item (`item`, `category`, `status: moved/keep`) | `moved`, `skipped`, `items[]`, `can_undo` |
| `undo` | files | Puts the most recent run back (repeat to go further back) | `restored`, `missing` |
| `open` | open | Opens the archive folder | `path` |

Parameters: `source` (`desktop`, `downloads`, `documents`, or a folder inside the home folder),
`library` (default Documents/桌面收纳 or Documents/Desktop Archive), `preset` (`zh-CN`/`en` category
names), `categories` (custom list of `{name, extensions, keywords}`; keywords win over extensions),
`group_by_month`, `include_folders` (default false), `min_age_seconds` (default 30).

Always left in place: shortcuts (.lnk .url .webloc), hidden and system files, half-finished
downloads, files changed in the last `min_age_seconds`, files another program has open, folders (unless
`include_folders`), apps. Names never clash: a second `report.pdf` becomes `report (2).pdf`.

## quit-apps · 一键收工 (Windows, macOS)

Asks open apps to quit the normal way, exactly like clicking their close button. Apps with unsaved work
show their own "save changes?" dialog and are reported as waiting. Nothing is ever force-quit.

| Op | Effect | What it does | Data |
|---|---|---|---|
| `status` | read | Counts apps that would be asked to quit | `open`, `kept`, `reopenable`, `available` |
| `preview` | read | Lists apps to close and apps that stay, with reasons | `apps[]`, `kept[]`, `count` |
| `run` | apps | Asks them to quit and waits up to `wait_seconds`; progress per app (`app`, `status: closed/hidden/waiting`) | `closed`, `waiting`, `skipped`, `apps[]` |
| `reopen` | apps | Opens again the apps closed by the last run | `opened` |

Always kept open: the system shell (Explorer, Finder, Dock), terminals, the AI tools (Claude, Codex,
ChatGPT), Python (the helper), wallpaper hosts, password managers, sync and backup, VPN and proxy
clients (Clash, V2Ray, …), security software, remote desktop, virtual machines, and the process tree
that runs the helper or the agent. Music players stay unless `keep_music` is false.

Parameters: `keep` (names, `.exe` names or macOS bundle ids to keep), `only` (close only these: e.g.
`["chrome.exe", "msedge.exe", "com.google.Chrome"]` for a "close browsers" button), `keep_music`
(default true), `close_folders` (Windows: also close File Explorer folder windows; default true),
`wait_seconds` (default 12).

On Windows, "hidden" means the app closed its windows but keeps running in the notification area
(chat apps often do this). Apps running as administrator cannot be asked by a normal process and are
reported as skipped.

## open-path · 打开 (Windows, macOS, Linux)

Opens a folder, a document or a web address: `path` accepts `{desktop}`, `{documents}`, `{downloads}`,
`{pictures}`, `{music}`, `{videos}`, `{home}`, `~/…`, absolute paths and `https://` addresses. `create`
makes a missing folder. Programs and scripts (.exe, .bat, .ps1, .app, .sh, …) are refused so a theme
button can never start software.

```html
<button data-orbit-action="open-path" data-orbit-params='{"path": "{documents}/Projects"}'>Projects</button>
```

## Composing new functions without code

| Wanted function | How |
|---|---|
| Tidy the Downloads folder | `tidy-files` with `{"source": "downloads"}` |
| File screenshots by month | `tidy-files` with `{"categories": [{"name": "Screenshots", "keywords": ["screenshot", "截图", "屏幕快照"]}], "group_by_month": true}` |
| Close only browsers | `quit-apps` with `{"only": ["chrome.exe", "msedge.exe", "firefox.exe", "com.google.chrome", "com.apple.safari"]}` |
| Focus mode: close chat apps | `quit-apps` with `{"only": ["wechat.exe", "qq.exe", "slack.exe", "discord.exe", "com.tencent.xinwechat"]}` |
| Open a project and its site | two `open-path` buttons |

Anything else (control music, start a timer that dims the scene, rename photos, back up a folder) is a
new action: see `action-guide.md`.
