"""Command line for people and for AI agents: python runtime/orbit.py <command>."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import VERSION, env, hosts, registry
from .config import Workspace
from .runner import merge_params, run_action
from .server import ping, serve

STATE_CHANGING = ("files", "apps", "system")


class Out:
    def __init__(self, lang: str):
        self.lang = lang

    def t(self, zh: str, en: str) -> str:
        return zh if self.lang.startswith("zh") else en

    def say(self, zh: str, en: str = "") -> None:
        print(self.t(zh, en or zh))


def _workspace(args: argparse.Namespace) -> Workspace:
    return Workspace(Path(args.workspace).expanduser().resolve() if getattr(args, "workspace", None) else None)


def _lang(ws: Workspace) -> str:
    return ws.load().get("language") or env.detect_language() if ws.exists() else env.detect_language()


def _port(ws: Workspace) -> int:
    return int(ws.load().get("port") or 47321)


def _require_helper(ws: Workspace, out: Out) -> bool:
    if ping(_port(ws)):
        return True
    ok, detail = hosts.start_background(ws)
    if not ok:
        out.say(f"桌面助手没有启动：{detail}", f"The helper did not start: {detail}")
    return ok


# --------------------------------------------------------------------------- commands

def cmd_init(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure(language=args.lang, theme=args.theme)
    out = Out(config["language"])
    out.say(f"工作区已就绪：{ws.root}", f"Workspace ready: {ws.root}")
    out.say(f"语言 {config['language']} · 当前主题 {config['active_theme']} · 端口 {config['port']}",
            f"Language {config['language']} · theme {config['active_theme']} · port {config['port']}")
    if not config.get("location"):
        out.say("提示：设置天气城市 → orbit.py set-location 上海", "Tip: set the weather place → orbit.py set-location \"New York\"")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    marks = {"ok": "✓", "warn": "!", "missing": "✗"}
    for status, item, detail in hosts.doctor(ws):
        print(f" {marks.get(status, '?')} {item:<18} {detail}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    ws.ensure()
    out = Out(_lang(ws))
    ok, detail = hosts.start_background(ws)
    if ok:
        out.say(f"桌面助手正在运行：{hosts.base_url(_port(ws))}/", f"Helper running at {hosts.base_url(_port(ws))}/")
        return 0
    out.say(f"启动失败：{detail}", f"Could not start: {detail}")
    return 1


def cmd_stop(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    out = Out(_lang(ws))
    stopped = hosts.stop_background(ws)
    out.say("桌面助手已停止。" if stopped else "没能停止桌面助手。", "Helper stopped." if stopped else "Could not stop the helper.")
    return 0 if stopped else 1


def cmd_serve(args: argparse.Namespace) -> int:
    return serve(_workspace(args), port=args.port, quiet=args.quiet)


def cmd_status(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    running = ping(config["port"])
    out.say(
        f"桌面助手：{'运行中' if running else '未运行'} · 主题：{config['active_theme']} · 地址：{hosts.base_url(config['port'])}/",
        f"Helper: {'running' if running else 'stopped'} · theme: {config['active_theme']} · {hosts.base_url(config['port'])}/",
    )
    return 0


def cmd_themes(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    lang = config["language"]
    for theme_id, theme in sorted(registry.load_themes(ws.root).items()):
        mark = "*" if theme_id == config.get("active_theme") else " "
        name = env.pick(theme.get("name"), lang, theme_id)
        print(f" {mark} {theme_id:<20} {name}  [{theme['_source']}]  {theme['_dir']}")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    themes = registry.load_themes(ws.root)
    if args.theme not in themes:
        out.say(f"找不到主题 {args.theme}。用 orbit.py themes 查看全部。", f"No theme '{args.theme}'. See: orbit.py themes")
        return 1
    ws.update(active_theme=args.theme)
    port = config["port"]
    if ping(port):
        _api_post(ws, "/api/theme/activate", {"id": args.theme})
    out.say(f"已切换到主题 {args.theme}。", f"Switched to theme {args.theme}.")
    return 0


def _api_post(ws: Workspace, path: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    import urllib.request

    config = ws.load()
    request = urllib.request.Request(
        f"{hosts.base_url(config['port'])}{path}",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "X-Orbit-Token": str(config.get("token") or "")},
    )
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def cmd_open(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    if not _require_helper(ws, out):
        return 1
    url = hosts.base_url(config["port"]) + (f"/themes/{args.theme}/" if args.theme else "/")
    how = hosts.open_preview(ws, url, fullscreen=not args.window)
    out.say(f"已打开预览（{how}）：{url}  · 全屏时按 F11 或 Alt+F4 退出",
            f"Preview opened ({how}): {url}  · press F11 or Alt+F4 to leave full screen")
    return 0


def cmd_gallery(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    if not _require_helper(ws, out):
        return 1
    url = hosts.base_url(config["port"]) + "/gallery"
    env.open_path(url)
    out.say(f"主题画廊：{url}", f"Theme gallery: {url}")
    return 0


def cmd_new_theme(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    if not registry.ID_PATTERN.match(args.id):
        out.say("主题 id 只能用小写字母、数字和连字符，例如 rainy-library。", "Theme ids use a-z, 0-9 and '-', e.g. rainy-library.")
        return 1
    target = ws.themes_dir / args.id
    if target.exists():
        out.say(f"{target} 已存在。", f"{target} already exists.")
        return 1
    source_name = args.source or "template"
    if source_name == "template":
        source = env.TEMPLATES_DIR / "theme"
    else:
        themes = registry.load_themes(ws.root)
        if source_name not in themes:
            out.say(f"找不到要复制的主题 {source_name}。", f"No theme '{source_name}' to copy.")
            return 1
        source = Path(themes[source_name]["_dir"])
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("preview.png", ".*"))
    manifest = env.read_json(target / "theme.json", {}) or {}
    manifest["id"] = args.id
    if args.name:
        manifest["name"] = args.name
    manifest.setdefault("version", "0.1.0")
    env.write_json(target / "theme.json", manifest)
    out.say(f"新主题已创建：{target}", f"New theme created: {target}")
    out.say("编辑 index.html / style.css / scene.js，然后运行 orbit.py validate " + args.id,
            "Edit index.html / style.css / scene.js, then run: orbit.py validate " + args.id)
    return 0


def _theme_folder(ws: Workspace, ref: str) -> Optional[Path]:
    path = Path(ref).expanduser()
    if (path / "theme.json").exists():
        return path.resolve()
    themes = registry.load_themes(ws.root)
    if ref in themes:
        return Path(themes[ref]["_dir"])
    return None


def cmd_validate(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    refs = args.themes or [config.get("active_theme")]
    actions = registry.load_actions(ws.root)
    worst = 0
    marks = {"ok": "✓", "warning": "!", "error": "✗"}
    for ref in refs:
        folder = _theme_folder(ws, str(ref))
        if folder is None:
            print(f" ✗ {ref}: not found")
            worst = 1
            continue
        print(f"{folder}")
        for level, message in registry.validate_theme(folder, actions):
            print(f"  {marks[level]} {message}")
            if level == "error":
                worst = 1
    return worst


def cmd_snapshot(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    folder = _theme_folder(ws, args.theme)
    if folder is None:
        out.say(f"找不到主题 {args.theme}。", f"No theme '{args.theme}'.")
        return 1
    if not _require_helper(ws, out):
        return 1
    try:
        width, height = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        out.say("--size 的格式是 1920x1080。", "--size looks like 1920x1080.")
        return 1
    theme_id = (env.read_json(folder / "theme.json", {}) or {}).get("id") or folder.name
    query = "snapshot=1" + ("" if args.live else "&demo=1") + ("&" + args.query.lstrip("?&") if args.query else "")
    url = f"{hosts.base_url(config['port'])}/themes/{theme_id}/?{query}"
    target = Path(args.out).expanduser() if args.out else folder / "preview.png"
    ok, detail = hosts.snapshot(url, target, width, height, args.wait)
    if ok:
        out.say(f"截图已保存：{detail}", f"Snapshot saved: {detail}")
        return 0
    out.say(f"截图失败：{detail}", f"Snapshot failed: {detail}")
    return 1


def cmd_actions(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    lang = ws.ensure()["language"]
    for action_id, manifest in sorted(registry.load_actions(ws.root).items()):
        summary = registry.summarize_action(manifest, lang)
        ops = ", ".join(f"{op}({spec['effect']})" for op, spec in summary["operations"].items())
        flag = "" if summary["supported"] else "  [not on " + env.PLATFORM + "]"
        print(f" {action_id:<16} {summary['name']} — {ops}  [{manifest['_source']}]{flag}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    lang = config["language"]
    out = Out(lang)
    actions = registry.load_actions(ws.root)
    manifest = actions.get(args.action)
    if manifest is None:
        out.say(f"找不到功能 {args.action}。用 orbit.py actions 查看全部。", f"No action '{args.action}'. See: orbit.py actions")
        return 1
    op = args.op
    effect = ((manifest.get("operations") or {}).get(op) or {}).get("effect", "read")
    if effect in STATE_CHANGING and not args.yes:
        out.say(
            f"“{args.action} {op}” 会真的改动你的电脑（{effect}）。确认要运行请加 --yes；只想看看会发生什么请用 preview。",
            f"'{args.action} {op}' really changes your computer ({effect}). Add --yes to run it, or use 'preview' to see what would happen.",
        )
        return 2
    try:
        requested = json.loads(args.params) if args.params else {}
    except ValueError:
        out.say("--params 需要是 JSON，例如 '{\"source\": \"downloads\"}'。", "--params must be JSON, e.g. '{\"source\": \"downloads\"}'.")
        return 1
    params = merge_params(manifest, ws.action_params(config, args.action), requested)

    def show_progress(event: Dict[str, Any]) -> None:
        if not args.json and event.get("message"):
            pct = event.get("progress")
            prefix = f"[{round(pct * 100):>3}%] " if isinstance(pct, (int, float)) else "       "
            print(prefix + str(event["message"]))

    result = run_action(manifest, op, params, lang=lang, workspace_root=ws.root, on_progress=show_progress)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(("✓ " if result.get("ok") else "✗ ") + str(result.get("message") or ""))
        data = result.get("data") or {}
        if data:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
    return 0 if result.get("ok") else 1


def cmd_new_action(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    if not registry.ID_PATTERN.match(args.id):
        out.say("功能 id 只能用小写字母、数字和连字符，例如 clean-downloads。", "Action ids use a-z, 0-9 and '-', e.g. clean-downloads.")
        return 1
    target = ws.actions_dir / args.id
    if target.exists():
        out.say(f"{target} 已存在。", f"{target} already exists.")
        return 1
    shutil.copytree(env.TEMPLATES_DIR / "action", target, ignore=shutil.ignore_patterns(".*", "__pycache__"))
    manifest = env.read_json(target / "action.json", {}) or {}
    manifest["id"] = args.id
    if args.name:
        manifest["name"] = args.name
    env.write_json(target / "action.json", manifest)
    out.say(f"新功能已创建：{target}", f"New action created: {target}")
    out.say(f"实现 action.py 后测试：orbit.py run {args.id} preview", f"Implement action.py, then test: orbit.py run {args.id} preview")
    return 0


def cmd_validate_action(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    folder = Path(args.action).expanduser()
    if not (folder / "action.json").exists():
        actions = registry.load_actions(ws.root)
        if args.action not in actions:
            print(f" ✗ {args.action}: not found")
            return 1
        folder = Path(actions[args.action]["_dir"])
    marks = {"ok": "✓", "warning": "!", "error": "✗"}
    worst = 0
    print(folder)
    for level, message in registry.validate_action(folder):
        print(f"  {marks[level]} {message}")
        worst = 1 if level == "error" else worst
    return worst


def cmd_set_location(args: argparse.Namespace) -> int:
    from . import weather

    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    try:
        places = weather.geocode(args.query, config["language"])
    except Exception as exc:
        out.say(f"查不到城市（网络问题？）：{exc}", f"Could not look up the place (network?): {exc}")
        return 1
    if not places:
        out.say("没有找到这个城市，换个写法试试（中文或英文都可以）。", "No match. Try another spelling.")
        return 1
    if args.pick is None and len(places) > 1 and sys.stdin.isatty():
        for index, place in enumerate(places, 1):
            print(f" {index}. {place['name']}, {place.get('admin1') or ''} {place.get('country') or ''}")
        try:
            choice = int(input(out.t("选择序号：", "Pick a number: ")).strip() or "1")
        except ValueError:
            choice = 1
    else:
        choice = args.pick or 1
    place = places[max(1, min(choice, len(places))) - 1]
    ws.update(location={k: place[k] for k in ("name", "latitude", "longitude", "timezone")})
    (ws.state_dir / "weather.json").unlink(missing_ok=True)
    out.say(f"天气城市已设为：{place['name']}（{place.get('country') or ''}）", f"Weather place set to {place['name']} ({place.get('country') or ''})")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    allowed = {"language": str, "units": str, "port": int}
    if args.key is None:
        shown = {k: v for k, v in config.items() if k != "token"}
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        return 0
    if args.key not in allowed:
        print(f"Settable keys: {', '.join(allowed)} (edit {ws.config_path} for the rest)")
        return 1
    if args.value is None:
        print(config.get(args.key))
        return 0
    value = allowed[args.key](args.value)
    if args.key == "units" and value not in ("metric", "imperial"):
        print("units is metric or imperial")
        return 1
    ws.update(**{args.key: value})
    print(f"{args.key} = {value}")
    return 0


def _put_on_desktop(ws: Workspace, out: Out) -> bool:
    config = ws.load()
    url = hosts.base_url(config["port"]) + "/"
    themes = registry.load_themes(ws.root)
    theme = themes.get(config.get("active_theme") or "")
    theme_dir = Path(theme["_dir"]) if theme else None
    if env.IS_WINDOWS:
        ok, detail = hosts.install_lively(ws, url, theme_dir)
        if ok:
            out.say("已通过 Lively Wallpaper 设为桌面。", "Set as your desktop with Lively Wallpaper.")
            return True
        if detail == "lively-missing":
            out.say(
                "需要先安装免费开源的 Lively Wallpaper（用来把网页放到桌面上）：\n"
                "  winget install -e --id rocksdanister.LivelyWallpaper\n"
                f"  或者打开 {hosts.LIVELY_WEBSITE} 下载。装好后再运行一次。",
                "Install the free, open-source Lively Wallpaper first (it places web pages on the desktop):\n"
                "  winget install -e --id rocksdanister.LivelyWallpaper\n"
                f"  or download it from {hosts.LIVELY_WEBSITE}. Then run this again.",
            )
            return False
        copied = hosts.copy_to_clipboard(url)
        out.say(
            "请在 Lively 里手动添加一次：打开 Lively → 点左上角 “+” → 在网址栏粘贴 "
            f"{url}{'（已复制）' if copied else ''} → 确定。",
            "Add it once by hand in Lively: open Lively → click '+' → paste "
            f"{url}{' (copied)' if copied else ''} into the URL box → OK.",
        )
        return False
    if env.IS_MAC:
        ok, detail = hosts.install_plash(url)
        if ok:
            out.say("已添加到 Plash。要点按桌面上的按钮，请在 Plash 菜单里打开“浏览模式”。",
                    "Added to Plash. To click buttons on the desktop, turn on Browsing Mode in the Plash menu.")
            return True
        out.say(f"需要先安装免费的 Plash：{hosts.PLASH_APP_STORE}，装好后再运行一次。",
                f"Install the free Plash app first: {hosts.PLASH_APP_STORE}, then run this again.")
        return False
    out.say(f"Linux 上请用支持网页壁纸的工具（如 Komorebi、Hidamari）加载：{url}",
            f"On Linux, load {url} with a web-wallpaper tool such as Komorebi or Hidamari.")
    return False


def cmd_install(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    if not _require_helper(ws, out):
        return 1
    placed = _put_on_desktop(ws, out)
    if not args.no_autostart:
        hosts.set_autostart(ws, True)
        out.say("已设置开机自动启动桌面助手（随时可用 orbit.py autostart off 关闭）。",
                "The helper now starts when you sign in (turn off with: orbit.py autostart off).")
    return 0 if placed else 3


def cmd_uninstall(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    out = Out(_lang(ws))
    hosts.set_autostart(ws, False)
    if env.IS_WINDOWS:
        hosts.uninstall_lively()
    hosts.stop_background(ws)
    out.say(
        f"已关闭开机启动并停止桌面助手。你的主题和设置仍保存在 {ws.root}。"
        + ("\nMac 上请在 Plash 的网站列表里删除 Orbit Desktop。" if env.IS_MAC else ""),
        f"Autostart removed and helper stopped. Your themes and settings stay in {ws.root}."
        + ("\nOn a Mac, remove Orbit Desktop from Plash's website list." if env.IS_MAC else ""),
    )
    return 0


def cmd_autostart(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    ws.ensure()
    out = Out(_lang(ws))
    if args.state == "status":
        out.say("开机启动：" + ("开" if hosts.autostart_enabled() else "关"), "Start at sign-in: " + ("on" if hosts.autostart_enabled() else "off"))
        return 0
    hosts.set_autostart(ws, args.state == "on")
    out.say("开机启动已" + ("打开" if args.state == "on" else "关闭") + "。", "Start at sign-in turned " + args.state + ".")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    folder = _theme_folder(ws, args.theme)
    if folder is None:
        print(f"No theme '{args.theme}'")
        return 1
    target = Path(args.out).expanduser() if args.out else Path.cwd() / f"{folder.name}.orbit-theme.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(folder).parts):
                archive.write(path, Path(folder.name) / path.relative_to(folder))
    print(target)
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    source = Path(args.source).expanduser()
    staging = ws.state_dir / "import"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    if source.is_dir():
        shutil.copytree(source, staging / source.name)
    else:
        with zipfile.ZipFile(source) as archive:
            for member in archive.namelist():
                resolved = (staging / member).resolve()
                if staging.resolve() not in resolved.parents:
                    out.say("压缩包里有不安全的路径，已拒绝。", "The archive contains unsafe paths; refused.")
                    return 1
            archive.extractall(staging)
    found = [p.parent for p in staging.rglob("theme.json")]
    if len(found) != 1:
        out.say("没有找到唯一的 theme.json。", "Expected exactly one theme.json.")
        return 1
    folder = found[0]
    report = registry.validate_theme(folder, registry.load_actions(ws.root))
    for level, message in report:
        print(f"  {level}: {message}")
    if any(level == "error" for level, _ in report):
        return 1
    theme_id = (env.read_json(folder / "theme.json", {}) or {}).get("id") or folder.name
    target = ws.themes_dir / theme_id
    if target.exists():
        out.say(f"{target} 已存在，先改名或删除。", f"{target} exists; rename or remove it first.")
        return 1
    shutil.move(str(folder), str(target))
    shutil.rmtree(staging, ignore_errors=True)
    out.say(f"已导入主题 {theme_id}。注意：主题是可执行的网页代码，只导入你信任的来源。",
            f"Imported theme {theme_id}. Themes are web code that can trigger your actions; only import from people you trust.")
    return 0


def cmd_quickstart(args: argparse.Namespace) -> int:
    """A small menu for people who double-clicked the start script."""
    ws = _workspace(args)
    config = ws.ensure()
    out = Out(config["language"])
    print()
    print("  ◯  Orbit Desktop " + VERSION)
    if not _require_helper(ws, out):
        input(out.t("按回车退出", "Press Enter to exit"))
        return 1
    url = hosts.base_url(config["port"]) + "/"
    out.say(f"  桌面助手已在后台运行：{url}", f"  The helper is running in the background: {url}")
    menu = [
        ("1", out.t("全屏预览当前主题", "Preview the current theme full screen")),
        ("2", out.t("打开主题画廊（换主题）", "Open the theme gallery (switch themes)")),
        ("3", out.t("设为桌面壁纸，并开机自动启动", "Put it on the desktop and start at sign-in")),
        ("4", out.t("设置天气城市", "Set the weather place")),
        ("5", out.t("停止桌面助手", "Stop the helper")),
        ("q", out.t("退出菜单（助手继续在后台运行）", "Leave this menu (the helper keeps running)")),
    ]
    while True:
        print()
        for key, label in menu:
            print(f"   {key}) {label}")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 0
        if choice == "1":
            hosts.open_preview(ws, url, fullscreen=True)
            out.say("  已打开。按 F11 退出全屏，Alt+F4 关闭。", "  Opened. F11 leaves full screen, Alt+F4 closes it.")
        elif choice == "2":
            env.open_path(hosts.base_url(config["port"]) + "/gallery")
        elif choice == "3":
            placed = _put_on_desktop(ws, out)
            hosts.set_autostart(ws, True)
            if placed:
                out.say("  完成。开机后桌面会自动出现。", "  Done. It will come back after you sign in.")
        elif choice == "4":
            try:
                query = input(out.t("  城市名（中文或英文）：", "  City name: ")).strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if query:
                ns = argparse.Namespace(workspace=args.workspace, query=query, pick=None)
                cmd_set_location(ns)
        elif choice == "5":
            hosts.stop_background(ws)
            out.say("  已停止。", "  Stopped.")
            return 0
        elif choice in ("q", "quit", "exit"):
            return 0


# --------------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orbit.py", description="Orbit Desktop: design and run a living, functional desktop.")
    parser.add_argument("--workspace", help="workspace folder (default ~/OrbitDesktop or $ORBIT_WORKSPACE)")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def add(name: str, func: Any, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

    p = add("init", cmd_init, "create the workspace and config")
    p.add_argument("--lang", choices=["zh-CN", "en"])
    p.add_argument("--theme")
    add("doctor", cmd_doctor, "check Python, the helper, browsers and the wallpaper host")
    add("start", cmd_start, "start the helper in the background")
    add("stop", cmd_stop, "stop the helper")
    p = add("serve", cmd_serve, "run the helper in the foreground")
    p.add_argument("--port", type=int)
    p.add_argument("--quiet", action="store_true")
    add("status", cmd_status, "show whether the helper runs and which theme is active")
    add("themes", cmd_themes, "list themes")
    p = add("use", cmd_use, "switch the active theme")
    p.add_argument("theme")
    p = add("open", cmd_open, "open a full-screen preview window")
    p.add_argument("theme", nargs="?")
    p.add_argument("--window", action="store_true", help="a normal window instead of full screen")
    add("gallery", cmd_gallery, "open the theme gallery in the browser")
    p = add("new-theme", cmd_new_theme, "create a theme in the workspace from the template or a copy of a theme")
    p.add_argument("id")
    p.add_argument("--from", dest="source", help="'template' (default) or a theme id to copy")
    p.add_argument("--name")
    p = add("validate", cmd_validate, "check themes for problems")
    p.add_argument("themes", nargs="*")
    p = add("snapshot", cmd_snapshot, "render a theme to a PNG (default: <theme>/preview.png)")
    p.add_argument("theme")
    p.add_argument("--out")
    p.add_argument("--size", default="1920x1080")
    p.add_argument("--wait", type=int, default=4000, help="milliseconds of animation before the shot")
    p.add_argument("--live", action="store_true", help="use real data instead of demo data")
    p.add_argument("--query", help="extra URL parameters, e.g. daypart=night&weather=rain")
    add("actions", cmd_actions, "list actions (desktop functions)")
    p = add("run", cmd_run, "run an action operation, e.g. run tidy-files preview")
    p.add_argument("action")
    p.add_argument("op", nargs="?", default="preview")
    p.add_argument("--params", help="JSON object of parameters")
    p.add_argument("--yes", action="store_true", help="allow operations that change files or apps")
    p.add_argument("--json", action="store_true")
    p = add("new-action", cmd_new_action, "create a new action in the workspace from the template")
    p.add_argument("id")
    p.add_argument("--name")
    p = add("validate-action", cmd_validate_action, "check an action folder")
    p.add_argument("action")
    p = add("set-location", cmd_set_location, "set the place used for weather")
    p.add_argument("query")
    p.add_argument("--pick", type=int)
    p = add("config", cmd_config, "show or set language, units or port")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p = add("install", cmd_install, "put the theme on the desktop and start the helper at sign-in")
    p.add_argument("--no-autostart", action="store_true")
    add("uninstall", cmd_uninstall, "remove autostart, take Orbit off the desktop and stop the helper")
    p = add("autostart", cmd_autostart, "start the helper at sign-in: on, off or status")
    p.add_argument("state", choices=["on", "off", "status"])
    p = add("export-theme", cmd_export, "zip a theme to share it")
    p.add_argument("theme")
    p.add_argument("--out")
    p = add("import-theme", cmd_import, "add a shared theme (zip or folder) to the workspace")
    p.add_argument("source")
    add("quickstart", cmd_quickstart, "interactive menu (used by the double-click start scripts)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    env.ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return int(args.func(args) or 0)
