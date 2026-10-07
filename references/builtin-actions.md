# Built-in actions

Operations marked *read* do not move user files or close apps; the helper may maintain its own state
directories. Use them while designing. Parameters can be
set per user in `~/OrbitDesktop/config.json`:

```json
{ "actions": { "quit-apps": { "params": { "keep": ["WeChat", "spotify.exe"] } },
               "tidy-files": { "params": { "library": "{documents}/Desktop Archive" } } } }
```

and per button in a theme with `data-orbit-params='{"source":"downloads"}'` (a theme can only set
parameters the action declares). Test any operation from the command line:
`orbit.py run <action> <op> [--param key=value ...] [--yes]`, for example
`orbit.py run tidy-files preview --param source=downloads`. `--param` works the same in every shell;
`--params '{...}'` also works, but Windows PowerShell 5.1 strips the quotes inside JSON.

## tidy-files · 一键收纳 (Windows, macOS, Linux)

Moves local loose files from a folder into category folders on the **same filesystem volume**. The
desktop is the default; Windows' known-folder lookup can locate a redirected desktop, which does not
imply full OneDrive or other cloud-provider support. Every attempted run is journaled. New journals
support checked undo; legacy journals without file identity evidence require manual review.

| Op | Effect | What it does | Data |
|---|---|---|---|
| `status` | read | Counts loose items, checks undo | `pending`, `kept`, `source`, `library`, `last_run`, `manual_review`, `available` |
| `preview` | read | Lists what would move where | `pending`, `by_category`, `items[]` |
| `run` | files | Moves them; progress per item (`item`, `category`, `status: moved/keep`) | `moved`, `skipped`, `items[]`, `can_undo` |
| `undo` | files | Restores verified items from the most recent unfinished run; retains failures for retry | `restored`, `missing`, `remaining`, `manual_review`, `items[]`, `can_undo` |
| `open` | open | Opens the archive folder | `path` |

Parameters: `source` (`desktop`, `downloads`, `documents`, or a folder inside the home folder),
`library` (default Documents/桌面收纳 or Documents/Desktop Archive), `preset` (`zh-CN`/`en` category
names), `categories` (custom list of `{name, extensions, keywords}`; keywords win over extensions),
`group_by_month`, `include_folders` (default false), `min_age_seconds` (default 30).

Category names must be single portable folder names: no absolute paths, `..`, separators, drive
prefixes or Windows reserved names. Archive paths are checked again before moving; category symlinks
and junctions are rejected. Source identity is checked after scanning and immediately before a move.

The scan skips recognized shortcuts (.lnk .url .webloc, etc.), hidden/system entries, partial download
suffixes, recently modified files, symlinks, and .app/.bundle directories. Detected Windows offline,
recall and reparse flags, macOS dataless flags, and `.icloud` placeholders are skipped without reading
their content. This detection is conservative and **does not cover every cloud provider**. On macOS
and Linux, available `lsof` checks skip detected open files; on Windows, locked files depend on OS
sharing permissions. Neither mechanism proves that every in-use file has been detected.

Folders stay by default. With `include_folders=true`, a folder and its descendants must pass recursive
local-content checks; a link, detected placeholder or unreadable descendant leaves the folder in
place. Large files/folders take longer because content is hashed. Cross-volume moves and unsupported
file moves are skipped, with the source preserved. Existing destination names receive a suffix such
as `report (2).pdf`.

Undo checks the recorded file identity, parent directory identities and SHA-256 content digest.
Changed or replaced items stay in the archive with an explanation. Successful restores are recorded
individually, so a temporary failure can be retried without moving successful items twice. Older
journals lacking this evidence are preserved and reported for manual review; they are not
automatically undone. The checks are intended to catch ordinary concurrent edits and changed paths;
they are not a filesystem sandbox against a hostile local process racing every check.

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
makes a missing folder. Known program, script and launcher extensions (.exe, .bat, .ps1, .app, .sh,
.py, .lnk, .webloc, etc.) are refused on both the requested path and its resolved target. POSIX files
with executable permission and paths inside .app/.workflow bundles are also refused. File opening
still uses the OS default handler: these checks are not a sandbox for every file association, and
ordinary documents may launch their associated application.

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
