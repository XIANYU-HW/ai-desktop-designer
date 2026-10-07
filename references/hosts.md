# Putting the theme on the desktop

The helper serves the active theme at `http://127.0.0.1:47321/` (port in config.json). A wallpaper host
shows that address behind the desktop icons. `orbit.py install` sets everything up; this page explains
what it does and how to do it by hand.

## Windows: Lively Wallpaper

[Lively Wallpaper](https://www.rocksdanister.com/lively/) is free and open source (GPL-3.0) and shows web
pages as the wallpaper, with mouse clicks passed through to the page.

1. Install it (ask the user first):
   `winget install -e --id rocksdanister.LivelyWallpaper`
   (or the installer from the website, or the Microsoft Store version).
2. `orbit.py install` then:
   - creates a Lively wallpaper entry `wallpapers\orbit-desktop\LivelyInfo.json` in Lively's library
     (`%LOCALAPPDATA%\Lively Wallpaper\Library` unless moved in Lively's settings) that points to the helper address;
   - runs `Lively.exe setwp --file <that folder>` to apply it;
   - adds the helper to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` so it starts at sign-in.
3. The Microsoft Store version cannot be driven from the command line. Add it by hand once: open Lively,
   click **+**, paste `http://127.0.0.1:47321/` into the address box and press Enter. `install` copies the
   address to the clipboard for this.

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

1. Install Plash (ask the user first).
2. `orbit.py install` opens `plash:add?url=http://127.0.0.1:47321/&title=Orbit%20Desktop` and adds a
   LaunchAgent (`~/Library/LaunchAgents/io.github.orbit-desktop.helper.plist`) that starts the helper at sign-in.
3. To click buttons on the desktop, turn on **Browsing Mode** in the Plash menu (or set a keyboard
   shortcut for it in Plash's settings). Turn it off again to use desktop icons.

## Any system: a preview window

`orbit.py open` opens the page in a chrome-less, full-screen window of Edge, Chrome, Chromium or Brave
(F11 leaves full screen). It is the quickest way to show a theme, and works on Linux too; on Linux any
web-wallpaper tool (for example Komorebi or Hidamari) can load the address.

## Start at sign-in

`orbit.py autostart on|off|status`. Windows uses the per-user Run key with `pythonw.exe` (no console
window); macOS a per-user LaunchAgent; Linux `~/.config/autostart/orbit-desktop.desktop`.

## Taking it all off

`orbit.py uninstall` removes autostart, closes and removes the Lively entry Orbit created, and stops the
helper. On macOS remove the address from Plash's website list. The workspace (`~/OrbitDesktop`) is kept;
delete it by hand only if the user asks.
