"""orbit.py review: look at a theme the way an art director would, before the user sees it.

It renders the theme in the screen sizes people really have and in its other states (day, night and
rain, English, any states the theme lists in theme.json under "review"), asks the page to measure
itself (sdk/orbit.js ?review: fonts, fallbacks, overlaps, tiny text, icon and taskbar zones, script
errors, network requests), and writes a folder with every picture plus report.md: the automatic
findings followed by the checklist from references/quality-review.md. The agent then opens every
picture and answers the checklist item by item; anything not at the bar gets fixed and reviewed again.
"""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import env, hosts

SIZES = [(1920, 1080), (1366, 768), (2560, 1440), (3440, 1440), (1280, 1024)]
STATES = [("day", "daypart=day"), ("night-rain", "daypart=night&weather=rain"), ("english", "lang=en")]
MIN_TEXT_PX = 11
MAX_TEXT_SIZES = 6
MAX_FAMILIES = 3
REVIEW_JSON = re.compile(r'<script[^>]*id="orbit-review"[^>]*>(.*?)</script>', re.S)

Finding = Tuple[str, str]   # (level: "error" | "warning" | "ok", message)


def theme_states(theme: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Extra states a theme wants reviewed, from theme.json: {"review": {"states": {"name": "query"}}}."""
    states = ((theme.get("review") or {}).get("states")) or {}
    out = []
    if isinstance(states, dict):
        for name, query in states.items():
            if isinstance(query, str):
                out.append((re.sub(r"[^a-z0-9-]+", "-", str(name).lower()).strip("-") or "state", query.lstrip("?&")))
    return out


def parse_report(dom: str) -> Optional[Dict[str, Any]]:
    match = REVIEW_JSON.search(dom or "")
    if not match:
        return None
    try:
        return json.loads(html.unescape(match.group(1)))
    except ValueError:
        return None


def network_sources(theme_dir: Path) -> List[str]:
    """Remote URLs written in the theme's own files (fonts, scripts, images loaded at run time)."""
    found = set()
    for path in theme_dir.rglob("*"):
        if path.suffix.lower() in (".html", ".css", ".js") and "fonts" not in path.parts:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for url in re.findall(r"""https?://[^\s"'()<>]+""", text):
                if "127.0.0.1" not in url and "localhost" not in url and not url.startswith("http://www.w3.org"):
                    found.add(url.split("?")[0])
    return sorted(found)


def assess(report: Optional[Dict[str, Any]], theme_dir: Path) -> List[Finding]:
    findings: List[Finding] = []
    if report is None:
        return [("error", "The page did not write its self-measurement: it may have crashed before the SDK ran, or the SDK is out of date.")]
    for message in report.get("errors") or []:
        findings.append(("error", f"Script error: {message}"))
    failed_fonts = sorted({f"{f['family']} {f.get('weight', '')}".strip() for f in report.get("fonts") or [] if f.get("status") == "error"})
    for font in failed_fonts:
        findings.append(("error", f"Font file failed to load: {font}"))
    missing = sorted(family for family, ok in (report.get("families") or {}).items() if not ok and family not in ("serif", "sans-serif", "monospace", "system-ui", "cursive", "fantasy"))
    for family in missing:
        findings.append(("error", f"Text is shown in a fallback font: '{family}' is not available. Bundle it (orbit.py fonts) or use a font every system has."))
    remote = sorted(set((report.get("network") or []) + network_sources(theme_dir)))
    if remote:
        findings.append(("warning", "Loads from the network at run time (breaks offline and where the host is blocked, e.g. Google Fonts in mainland China): "
                         + ", ".join(remote[:6]) + (" …" if len(remote) > 6 else "") + ". Bundle fonts with orbit.py fonts; ship other files in assets/."))
    for a, b in report.get("overlaps") or []:
        findings.append(("error", f"Overlap: {a} and {b}"))
    zones: Dict[str, List[str]] = {}
    for item in report.get("zones") or []:
        zones.setdefault(item["zone"], []).append(item["el"])
    for zone, items in zones.items():
        findings.append(("warning", f"Text in the {zone} area: " + "; ".join(items[:5]) + (" …" if len(items) > 5 else "")))
    for el in (report.get("offscreen") or [])[:5]:
        findings.append(("error", f"Outside the screen: {el}"))
    texts = report.get("text") or []
    tiny = sorted({f"{t['el']} ({t['size']}px)" for t in texts if t.get("size", 99) < MIN_TEXT_PX})
    if tiny:
        findings.append(("warning", f"Text smaller than {MIN_TEXT_PX}px at {report['viewport'][0]}×{report['viewport'][1]}: " + "; ".join(tiny[:5])))
    sizes = sorted({round(t["size"]) for t in texts})
    if len(sizes) > MAX_TEXT_SIZES:
        findings.append(("warning", f"{len(sizes)} different text sizes ({', '.join(str(s) for s in sizes)}px): a premium page uses a short scale (display, title, text, caption)."))
    families = sorted({t["family"] for t in texts})
    if len(families) > MAX_FAMILIES:
        findings.append(("warning", f"{len(families)} font families ({', '.join(families)}): keep to one display voice and one text face."))
    if not report.get("translate"):
        findings.append(("warning", "The page can be offered for translation: add translate=\"no\" to <html> (current SDKs do this)."))
    if not findings:
        findings.append(("ok", "No automatic problems found."))
    return findings


def checklist(skill_dir: Path) -> str:
    path = skill_dir / "references" / "quality-review.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r"## The checklist\n(.*)", text, re.S)
    return match.group(1).strip() if match else text


def run(
    theme_dir: Path,
    theme: Dict[str, Any],
    port: int,
    out_dir: Path,
    *,
    quick: bool = False,
    wait_ms: int = 4500,
    log: Callable[[str], None] = print,
) -> Tuple[int, Path]:
    """Render, measure and write the report. Returns (worst level: 0 ok, 1 warnings, 2 errors, report path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    theme_id = theme.get("id") or theme_dir.name
    base = f"{hosts.base_url(port)}/themes/{theme_id}/?snapshot=1&demo=1"
    sizes = SIZES[:2] if quick else SIZES
    plan: List[Tuple[str, str, int, int]] = [("default", "", w, h) for w, h in sizes]
    for name, query in STATES + theme_states(theme):
        plan.append((name, query, 1920, 1080))
    pictures: List[Tuple[str, Path]] = []
    for name, query, width, height in plan:
        target = out_dir / f"{name}-{width}x{height}.png"
        ok, detail = hosts.snapshot(base + ("&" + query if query else ""), target, width, height, wait_ms)
        log(("  ✓ " if ok else "  ✗ ") + (target.name if ok else f"{target.name}: {detail}"))
        if ok:
            pictures.append((f"{name} · {width}×{height}" + (f" · ?{query}" if query else ""), target))
    measured: Dict[str, Optional[Dict[str, Any]]] = {}
    for width, height in sizes[:2]:
        ok, dom = hosts.dump_dom(base + "&review=3500", width, height, wait_ms + 2500)
        measured[f"{width}x{height}"] = parse_report(dom) if ok else None
    findings: List[Finding] = []
    for size, report in measured.items():
        for level, message in assess(report, theme_dir):
            entry = (level, f"[{size}] {message}" if level != "ok" else message)
            if entry not in findings:
                findings.append(entry)
    if any(level != "ok" for level, _ in findings):
        findings = [f for f in findings if f[0] != "ok"]
    worst = 2 if any(level == "error" for level, _ in findings) else 1 if any(level == "warning" for level, _ in findings) else 0
    marks = {"ok": "✓", "warning": "!", "error": "✗"}
    lines = [
        f"# Review of {theme_id} — {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Open every picture below and answer the checklist with what you actually see. Fix what is not at",
        "the bar, run `orbit.py review` again, and only then show the user. After installing, check the real",
        "desktop too: `orbit.py capture` (with the user's OK) and look at the picture.",
        "",
        "## Automatic findings",
        "",
    ]
    lines += [f"- {marks[level]} {message}" for level, message in findings]
    lines += ["", "## Pictures", ""]
    lines += [f"- {label}: `{path.name}`" for label, path in pictures]
    lines += ["", "## Checklist (answer every item)", "", checklist(env.SKILL_ROOT) or "See references/quality-review.md."]
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps({"theme": theme_id, "findings": findings, "measured": measured,
                                                      "pictures": [str(p) for _, p in pictures]}, ensure_ascii=False, indent=1), encoding="utf-8")
    return worst, report_path
