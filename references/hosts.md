# Putting the theme on the desktop

The helper serves the active theme at `http://127.0.0.1:47321/` (port in config.json). A wallpaper host
shows that address behind the desktop icons. `orbit.py install` starts the helper and submits a host
request. A successful command means the request was accepted; confirm the actual desktop separately.
Start at sign-in is unchanged unless `--autostart` is explicitly supplied.

## Windows: Lively Wallpaper

[Lively Wallpaper](https://www.rocksdanister.com/lively/) is free and open source (GPL-3.0) and shows web
pages as the wallpaper, with mouse clicks passed through to the page.

1. Install it when covered by the user’s authorization:
   `winget install -e --id rocksdanister.LivelyWallpaper`
   (or the installer from the website, or the Microsoft Store version).
2. `orbit.py install` then:
   - creates a Lively wallpaper entry `wallpapers\orbit-desktop\LivelyInfo.json` in Lively's library
     (`%LOCALAPPDATA%\Lively Wallpaper\Library` unless moved in Lively's settings) that points to the helper address;
   - runs `Lively.exe setwp --file <that folder>` and checks the command's exit status;
   - only with `--autostart`, and after that request succeeds, adds the helper to
     `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` so it starts at sign-in.
3. The Microsoft Store version cannot be driven from the command line. `install` still puts the Orbit
   Desktop entry into its library, so the user only has to open Lively and click **Orbit Desktop** there.
   Do not tell them to add it with **+**: that creates a second entry. Only if the entry is missing after
   quitting and reopening Lively, click **+** and paste `http://127.0.0.1:47321/` (`install` copies it).

Good to know:

- Lively pauses the wallpaper when an app is maximized or full screen (its default); the SDK receives the
  pause event and stops animating.
- Mouse input reaches the page by default (Lively settings → Wallpaper → Interaction). Keyboard input is
  off by default, so themes should not depend on typing.
- Clicks only reach the page where no desktop icon is. A busy desktop can hide its icons from Lively:
  `Lively.exe app --showIcons false` (ask the user; `true` brings them back).
- Every monitor gets its own copy of the page; themes must work at any size.
- If the page shows an error after sign-in, the helper started after Lively. `orbit.py start`, then
  right-click Lively's tray icon and reload, or run `Lively.exe setwp --file reload`.

## macOS: Plash

[Plash](https://apps.apple.com/app/plash/id1494023538) is a free App Store app that shows a website as the wallpaper.

1. Install Plash when covered by the user’s authorization.
2. `orbit.py install` submits `plash:add?url=http://127.0.0.1:47321/&title=Orbit%20Desktop` through macOS
   and checks the command's exit status. Confirm Orbit Desktop appears in Plash's website list and on
   the desktop. Only `install --autostart`, after the request succeeds, adds a LaunchAgent
   (`~/Library/LaunchAgents/io.github.orbit-desktop.helper.plist`) for the helper at sign-in.
3. To click buttons on the desktop, turn on **Browsing Mode** in the Plash menu (or set a keyboard
   shortcut for it in Plash's settings). Turn it off again to use desktop icons.

## Any system: a preview window

`orbit.py open` opens the page in a chrome-less, full-screen window of Edge, Chrome, Chromium or Brave
(F11 leaves full screen). It is the quickest way to show a theme, and works on Linux too; on Linux any
web-wallpaper tool (for example Komorebi or Hidamari) can load the address.

## Start at sign-in

`orbit.py autostart on|off|status`. Windows uses the per-user Run key with `pythonw.exe` (no console
window); macOS a per-user LaunchAgent; Linux `~/.config/autostart/orbit-desktop.desktop`.
Every background and sign-in command records the resolved workspace path, including a workspace
selected with `--workspace`. `install --no-autostart` remains accepted for compatibility and has the
same sign-in behavior as plain `install`: existing start-at-sign-in settings are left unchanged.
Use `autostart off` to disable an existing setting. The interactive menu's desktop option explicitly
includes start at sign-in, and enables it only after the host request succeeds.

## Taking it all off

`orbit.py uninstall` removes autostart and stops the helper. In Lively, close and delete only the
**Orbit Desktop** entry by hand. The runtime cannot verify which monitors currently show Orbit, so it
does not issue a command that closes every wallpaper or remove potentially active library files.
On macOS remove Orbit Desktop from Plash's website list. The workspace (`~/OrbitDesktop`) is kept;
delete it by hand only if the user asks.

Exit code `0` means the requested automated steps succeeded. For `install`, this confirms request
acceptance, not the actual desktop display. Exit code `3` means setup or removal still needs a manual
host step (including a missing host or rejected setup request); exit code `1` means the helper or
start-at-sign-in operation failed. Read the accompanying message for the remaining step. Uninstall
does not claim to restore a previous wallpaper.
