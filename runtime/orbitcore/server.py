"""The local helper: serves themes to the wallpaper host and runs actions for them.

It listens on 127.0.0.1 only. Every API call needs the per-install token that
is written into theme pages when they are served, the Host header must be the
loopback address (blocks DNS rebinding), and cross-site browser requests are
refused (no CORS headers, Origin checked). A web page you visit cannot make
your desktop tidy files or close apps.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import queue
import re
import secrets
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import VERSION, env, registry, system, weather
from .config import Workspace
from .runner import merge_params, run_action

log = logging.getLogger("orbit.server")

MIME_OVERRIDES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".glb": "model/gltf-binary",
    ".wasm": "application/wasm",
}
MAX_BODY = 64 * 1024


class EventBus:
    """Fan-out of server-sent events to every open desktop page."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: "set[queue.Queue[Tuple[str, str]]]" = set()

    def subscribe(self) -> "queue.Queue[Tuple[str, str]]":
        q: "queue.Queue[Tuple[str, str]]" = queue.Queue(maxsize=512)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "queue.Queue[Tuple[str, str]]") -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: str, data: Dict[str, Any]) -> None:
        payload = (event, json.dumps(data, ensure_ascii=False))
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass


class App:
    def __init__(self, workspace: Workspace, port: int):
        self.workspace = workspace
        self.port = port
        self.bus = EventBus()
        self.started = time.time()
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self.stop_event = threading.Event()
        self.reload()

    # configuration -----------------------------------------------------------
    def reload(self) -> None:
        self.config = self.workspace.load()
        self.token = str(self.config.get("token") or "")
        self.lang = self.config.get("language") or env.detect_language()
        self.themes = registry.load_themes(self.workspace.root)
        self.actions = registry.load_actions(self.workspace.root)

    @property
    def allowed_hosts(self) -> "set[str]":
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    @property
    def allowed_origins(self) -> "set[str]":
        return {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}

    def active_theme_id(self) -> Optional[str]:
        wanted = self.config.get("active_theme")
        if wanted in self.themes:
            return wanted
        return next(iter(sorted(self.themes)), None)

    def state(self) -> Dict[str, Any]:
        self.reload()
        return {
            "ok": True,
            "app": "orbit-desktop",
            "version": VERSION,
            "platform": env.PLATFORM,
            "language": self.lang,
            "active_theme": self.active_theme_id(),
            "themes": [registry.summarize_theme(t, self.lang) for t in sorted(self.themes.values(), key=lambda t: t["id"])],
            "actions": {aid: registry.summarize_action(m, self.lang) for aid, m in sorted(self.actions.items())},
            "config": {
                "language": self.lang,
                "units": self.config.get("units") or "metric",
                "location": (self.config.get("location") or {}).get("name"),
            },
        }

    def action_lock(self, action_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(action_id, threading.Lock())

    # actions -----------------------------------------------------------------
    def run(self, action_id: str, op: str, requested: Dict[str, Any], client: str) -> Tuple[int, Dict[str, Any]]:
        self.reload()
        manifest = self.actions.get(action_id)
        if manifest is None:
            return 404, {"ok": False, "message": "unknown action", "error": "unknown-action"}
        effect = ((manifest.get("operations") or {}).get(op) or {}).get("effect", "read")
        # Read-only operations (status, preview) may run alongside anything; changes run one at a time.
        lock = self.action_lock(action_id) if effect != "read" else threading.Lock()
        if not lock.acquire(blocking=False):
            return 409, {"ok": False, "message": ("这个功能正在运行。" if self.lang.startswith("zh") else "This action is already running."), "error": "busy"}
        run_id = secrets.token_hex(6)
        base = {"action": action_id, "op": op, "run": run_id, "client": client}
        try:
            params = merge_params(manifest, self.workspace.action_params(self.config, action_id), requested)
            self.bus.publish("action", dict(base, phase="start"))
            result = run_action(
                manifest, op, params,
                lang=self.lang,
                workspace_root=self.workspace.root,
                on_progress=lambda event: self.bus.publish("action", dict(base, phase="progress", **event)),
            )
            self.bus.publish("action", dict(base, phase="done" if result.get("ok") else "error", result=result))
            return 200, result
        finally:
            lock.release()


# ---------------------------------------------------------------------------

def _inject(html: str, app: App, theme_id: str) -> str:
    tags = (
        f'<meta name="orbit-token" content="{app.token}">'
        f'<meta name="orbit-lang" content="{app.lang}">'
        f'<meta name="orbit-theme" content="{theme_id}">'
        f'<meta name="orbit-platform" content="{env.PLATFORM}">'
    )
    match = re.search(r"<head[^>]*>", html, re.I)
    if match:
        return html[: match.end()] + tags + html[match.end():]
    return tags + html


def make_handler(app: App) -> "type[BaseHTTPRequestHandler]":
    class Handler(BaseHTTPRequestHandler):
        server_version = f"OrbitDesktop/{VERSION}"
        sys_version = ""

        def log_message(self, fmt: str, *args: Any) -> None:  # never write to a missing console
            log.debug("%s - %s", self.address_string(), fmt % args)

        # helpers -------------------------------------------------------------
        def _send(self, status: int, body: bytes, content_type: str, extra: Optional[Dict[str, str]] = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, data: Dict[str, Any]) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _deny(self, status: int = 403, why: str = "forbidden") -> None:
            self._json(status, {"ok": False, "error": why})

        def _host_ok(self) -> bool:
            return (self.headers.get("Host") or "").lower() in app.allowed_hosts

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            return origin is None or origin in app.allowed_origins

        def _token_ok(self, query: Dict[str, Any]) -> bool:
            supplied = self.headers.get("X-Orbit-Token") or ""
            if not supplied and self.path.startswith("/api/events"):
                supplied = (query.get("token") or [""])[0]
            return bool(app.token) and secrets.compare_digest(supplied, app.token)

        def _read_json(self) -> Optional[Dict[str, Any]]:
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return None
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return None
            if length > MAX_BODY:
                return None
            raw = self.rfile.read(length) if length else b"{}"
            try:
                value = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return None
            return value if isinstance(value, dict) else None

        def _static(self, base: Path, relative: str, theme_id: Optional[str] = None) -> None:
            relative = urllib.parse.unquote(relative)
            parts = [p for p in relative.split("/") if p not in ("", ".")]
            if any(p.startswith(".") or p == ".." for p in parts):
                return self._deny(404, "not-found")
            target = (base / Path(*parts)) if parts else base
            try:
                target = target.resolve()
                base_resolved = base.resolve()
            except OSError:
                return self._deny(404, "not-found")
            if target != base_resolved and base_resolved not in target.parents:
                return self._deny(404, "not-found")
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                return self._deny(404, "not-found")
            suffix = target.suffix.lower()
            content_type = MIME_OVERRIDES.get(suffix) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            body = target.read_bytes()
            if theme_id and suffix in (".html", ".htm"):
                body = _inject(body.decode("utf-8", errors="replace"), app, theme_id).encode("utf-8")
            self._send(200, body, content_type)

        # routing -------------------------------------------------------------
        def do_HEAD(self) -> None:
            self.do_GET()

        def do_OPTIONS(self) -> None:
            self._deny(403, "cross-origin requests are not allowed")

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._deny(403, "bad-host")
            url = urllib.parse.urlsplit(self.path)
            path, query = url.path, urllib.parse.parse_qs(url.query)

            if path == "/":
                theme_id = app.active_theme_id()
                if not theme_id:
                    return self._send(200, b"No theme installed.", "text/plain; charset=utf-8")
                self.send_response(302)
                self.send_header("Location", f"/themes/{theme_id}/?live=1")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path == "/api/ping":
                return self._json(200, {"ok": True, "app": "orbit-desktop", "version": VERSION, "pid": os.getpid()})
            if path.startswith("/sdk/"):
                return self._static(env.SDK_DIR, path[len("/sdk/"):])
            if path in ("/gallery", "/gallery/"):
                return self._static(env.SDK_DIR, "gallery.html", theme_id="gallery")
            match = re.match(r"^/themes/([a-z0-9-]+)(/.*)?$", path)
            if match:
                theme_id, rest = match.group(1), match.group(2)
                app.reload()
                theme = app.themes.get(theme_id)
                if theme is None:
                    return self._deny(404, "unknown-theme")
                if rest is None:
                    self.send_response(301)
                    self.send_header("Location", f"/themes/{theme_id}/" + (("?" + url.query) if url.query else ""))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                relative = rest.lstrip("/") or str(theme.get("entry") or "index.html")
                return self._static(Path(theme["_dir"]), relative, theme_id=theme_id)

            if not path.startswith("/api/"):
                return self._deny(404, "not-found")
            if not self._token_ok(query):
                return self._deny(401, "token-required")
            if path == "/api/state":
                return self._json(200, app.state())
            if path == "/api/system":
                return self._json(200, dict(system.readings(), ok=True))
            if path == "/api/weather":
                app.reload()
                return self._json(200, weather.get(app.config, app.workspace.state_dir / "weather.json"))
            if path == "/api/events":
                return self._events()
            return self._deny(404, "not-found")

        def do_POST(self) -> None:
            if not self._host_ok():
                return self._deny(403, "bad-host")
            if not self._origin_ok():
                return self._deny(403, "bad-origin")
            url = urllib.parse.urlsplit(self.path)
            if not self._token_ok({}):
                return self._deny(401, "token-required")
            body = self._read_json()
            if body is None:
                return self._deny(400, "json-body-required")
            path = url.path
            client = (self.headers.get("X-Orbit-Client") or "")[:40]

            match = re.match(r"^/api/actions/([a-z0-9-]+)/([a-z0-9-]+)$", path)
            if match:
                params = body.get("params") if isinstance(body.get("params"), dict) else {}
                status, result = app.run(match.group(1), match.group(2), params, client)
                return self._json(status, result)
            if path == "/api/theme/activate":
                app.reload()
                theme_id = str(body.get("id") or "")
                if theme_id not in app.themes:
                    return self._deny(404, "unknown-theme")
                app.workspace.update(active_theme=theme_id, theme_source="user")
                app.reload()
                app.bus.publish("theme-changed", {"id": theme_id})
                return self._json(200, {"ok": True, "active_theme": theme_id})
            if path == "/api/gallery/open":
                env.open_path(f"http://127.0.0.1:{app.port}/gallery")
                return self._json(200, {"ok": True})
            if path == "/api/shutdown":
                self._json(200, {"ok": True})
                threading.Thread(target=app.stop_event.set, daemon=True).start()
                return
            return self._deny(404, "not-found")

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            q = app.bus.subscribe()
            try:
                self.wfile.write(b"retry: 3000\n\nevent: hello\ndata: {}\n\n")
                self.wfile.flush()
                while not app.stop_event.is_set():
                    try:
                        event, data = q.get(timeout=15)
                        chunk = f"event: {event}\ndata: {data}\n\n"
                    except queue.Empty:
                        chunk = ": keep-alive\n\n"
                    self.wfile.write(chunk.encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                app.bus.unsubscribe(q)

    return Handler


class OrbitHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR would let a second server steal the port.
    allow_reuse_address = not env.IS_WINDOWS

    def server_bind(self) -> None:
        if env.IS_WINDOWS and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # HTTPServer.server_bind would call socket.getfqdn(), a reverse DNS lookup that can
        # stall for a long time on some machines. A loopback server does not need it.
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port


def _watch_themes(app: App) -> None:
    """Reload open desktop pages when theme files change, so edits show up live."""
    seen: Dict[str, float] = {}
    while not app.stop_event.wait(1.5):
        try:
            themes = registry.load_themes(app.workspace.root)
        except Exception:
            continue
        for theme_id, theme in themes.items():
            newest = 0.0
            for path in Path(theme["_dir"]).rglob("*"):
                try:
                    if path.is_file():
                        newest = max(newest, path.stat().st_mtime)
                except OSError:
                    continue
            if theme_id in seen and newest > seen[theme_id]:
                app.bus.publish("theme-updated", {"id": theme_id})
            seen[theme_id] = newest


def _setup_logging(workspace: Workspace) -> None:
    workspace.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = workspace.logs_dir / "orbit.log"
    try:
        if log_path.exists() and log_path.stat().st_size > 2 * 1024 * 1024:
            log_path.replace(workspace.logs_dir / "orbit.old.log")
    except OSError:
        pass
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    if sys.stdout is None or sys.stderr is None:  # pythonw.exe has no console
        stream = open(workspace.logs_dir / "console.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream


def ping(port: int, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
    import urllib.request

    try:
        request = urllib.request.Request(f"http://127.0.0.1:{port}/api/ping", headers={"Host": f"127.0.0.1:{port}"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never send loopback through a proxy
        with opener.open(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if data.get("app") == "orbit-desktop" else None
    except Exception:
        return None


def serve(workspace: Workspace, port: Optional[int] = None, quiet: bool = False) -> int:
    config = workspace.ensure()
    port = int(port or config.get("port") or 47321)
    if ping(port):
        if not quiet:
            print(f"Orbit Desktop is already running at http://127.0.0.1:{port}/")
        return 0
    _setup_logging(workspace)
    # If start-up ever stalls, write where it is stuck into the log instead of hanging silently.
    import faulthandler
    watchdog = open(workspace.logs_dir / "startup-stall.log", "w", encoding="utf-8")
    faulthandler.dump_traceback_later(12, exit=False, file=watchdog)
    app = App(workspace, port)
    try:
        httpd = OrbitHTTPServer(("127.0.0.1", port), make_handler(app))
    except OSError as exc:
        message = f"Port {port} is busy ({exc}). Change 'port' in {workspace.config_path} and try again."
        log.error(message)
        if not quiet:
            print(message)
        return 2
    env.write_json(workspace.server_file, {"pid": os.getpid(), "port": port, "started": time.time(), "version": VERSION})
    threading.Thread(target=_watch_themes, args=(app,), daemon=True).start()
    server_thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
    server_thread.start()
    log.info("serving on 127.0.0.1:%s (workspace %s)", port, workspace.root)
    faulthandler.cancel_dump_traceback_later()
    watchdog.close()
    if not quiet:
        print(f"Orbit Desktop is running at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        while not app.stop_event.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        app.stop_event.set()
        httpd.shutdown()
        httpd.server_close()
        try:
            data = env.read_json(workspace.server_file, {}) or {}
            if data.get("pid") == os.getpid():
                workspace.server_file.unlink()
        except OSError:
            pass
        log.info("stopped")
    return 0
