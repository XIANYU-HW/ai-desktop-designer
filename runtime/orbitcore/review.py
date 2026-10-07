"""Collect reproducible render evidence; visual quality and real-host behavior need separate review."""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

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
        value = json.loads(html.unescape(match.group(1)))
        return value if isinstance(value, dict) else None
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
    viewport = report.get("viewport")
    if not isinstance(viewport, list) or len(viewport) != 2 or not all(isinstance(n, (int, float)) and n > 0 for n in viewport):
        return [("error", "The page wrote an invalid measurement (missing or invalid viewport).")]
    for message in report.get("errors") or []:
        findings.append(("error", f"Script error: {message}"))
    failed_fonts = sorted({f"{f['family']} {f.get('weight', '')}".strip() for f in report.get("fonts") or [] if f.get("status") == "error"})
    for font in failed_fonts:
        findings.append(("error", f"Font file failed to load: {font}"))
    missing = sorted(family for family, ok in (report.get("families") or {}).items() if not ok and family not in ("serif", "sans-serif", "monospace", "system-ui", "cursive", "fantasy"))
    for family in missing:
        findings.append(("error", f"Font availability probe could not find '{family}'. Check the rendered glyphs and intended fallback; bundle required fonts if licensed. This probe cannot identify every glyph's actual font."))
    remote = sorted(set((report.get("network") or []) + network_sources(theme_dir)))
    if remote:
        findings.append(("warning", "Remote URLs observed or referenced in source (source references may be links or comments, not loads): "
                         + ", ".join(remote[:6]) + (" …" if len(remote) > 6 else "") + ". Inspect essential dependencies and test the offline state."))
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
        findings.append(("warning", f"{len(sizes)} different text sizes ({', '.join(str(s) for s in sizes)}px): inspect hierarchy against the chosen visual direction."))
    families = sorted({t["family"] for t in texts})
    if len(families) > MAX_FAMILIES:
        findings.append(("warning", f"{len(families)} font families ({', '.join(families)}): inspect whether each has an intentional role."))
    if not report.get("translate"):
        findings.append(("warning", "The page lacks translate=\"no\". This hint can reduce prompts, but only real browser/host input testing can verify translation behavior."))
    if not findings:
        findings.append(("ok", "No problems detected by these automatic probes; visual and host review remain pending."))
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
    """Render and measure every planned case. 0/1/2 means automatic ok/warning/error only."""
    out_dir.mkdir(parents=True, exist_ok=True)
    theme_id = theme.get("id") or theme_dir.name
    base = f"{hosts.base_url(port)}/themes/{theme_id}/?snapshot=1&demo=1"
    sizes = SIZES[:2] if quick else SIZES
    states = [("default", "")] + STATES + theme_states(theme)
    plan = [(name, query, w, h) for name, query in states for w, h in sizes]
    pictures: List[Tuple[str, Path]] = []
    measured: Dict[str, Optional[Dict[str, Any]]] = {}
    cases: List[Dict[str, Any]] = []
    findings: List[Finding] = []
    for number, (name, query, width, height) in enumerate(plan, 1):
        # Prefixes keep duplicate/sanitized state names from overwriting earlier evidence.
        case_id = f"{number:02d}-{name}-{width}x{height}"
        target = out_dir / f"{case_id}.png"
        url = base + ("&" + query if query else "")
        try:
            ok, detail = hosts.snapshot(url, target, width, height, wait_ms)
        except (OSError, RuntimeError) as exc:
            ok, detail = False, str(exc)
        if ok and (not target.is_file() or target.stat().st_size == 0):
            ok, detail = False, "the renderer reported success without a nonempty image"
        log(("  ✓ " if ok else "  ✗ ") + (target.name if ok else f"{target.name}: {detail}"))
        if ok:
            pictures.append((f"{name} · {width}×{height}" + (f" · ?{query}" if query else ""), target))
        else:
            findings.append(("error", f"[{case_id}] Snapshot failed: {detail}"))
        try:
            dom_ok, dom = hosts.dump_dom(url + "&review=3500", width, height, wait_ms + 2500)
        except (OSError, RuntimeError) as exc:
            dom_ok, dom = False, str(exc)
        report = parse_report(dom) if dom_ok else None
        measured[case_id] = report
        try:
            case_findings = assess(report, theme_dir)
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            case_findings = [("error", f"The page wrote malformed measurement fields: {exc}")]
        if report:
            expected_state = parse_qs(query).get("review-state", [None])[0]
            if expected_state and report.get("state") != expected_state:
                case_findings.append(("error", f"Fixture '{expected_state}' was requested but the page did not confirm data-review-state. Implement the state before claiming coverage."))
            # Some headless engines subtract window chrome from the requested size.
            if report.get("viewport") != [width, height]:
                case_findings.append(("warning", f"Requested {width}×{height}; browser measured {report.get('viewport')}. Use the measured viewport when recording coverage."))
        for level, message in case_findings:
            entry = (level, f"[{case_id}] {message}" if level != "ok" else message)
            if entry not in findings:
                findings.append(entry)
        cases.append({"id": case_id, "state": name, "query": query,
                      "requested_viewport": [width, height], "measured_viewport": report.get("viewport") if report else None,
                      "snapshot": "captured" if ok else "failed", "snapshot_error": None if ok else detail,
                      "measurement": "collected" if report is not None else "failed",
                      "measurement_error": None if dom_ok else dom,
                      "picture": str(target) if ok else None})
    if any(level != "ok" for level, _ in findings):
        findings = [f for f in findings if f[0] != "ok"]
    worst = 2 if any(level == "error" for level, _ in findings) else 1 if any(level == "warning" for level, _ in findings) else 0
    coverage = {"planned": len(plan), "captured": len(pictures),
                "measured": sum(r is not None for r in measured.values()), "mode": "quick" if quick else "full"}
    evidence = {"automatic": "failed" if worst == 2 else "warnings" if worst == 1 else "passed",
                "visual": "pending", "interaction": "pending", "real_host": "pending"}
    marks = {"ok": "✓", "warning": "!", "error": "✗"}
    lines = [
        f"# Review of {theme_id} — {time.strftime('%Y-%m-%d %H:%M')}", "",
        f"Automatic checks: **{evidence['automatic']}**. Visual, interaction and real-host review: **pending**.",
        f"Coverage ({coverage['mode']}): {len(plan)} planned cases; {len(pictures)} images; {coverage['measured']} page measurements.", "",
        "Screenshots and DOM probes do not certify aesthetics, frame pacing, input behavior or host installation.",
        "Inspect each image against the brief. Record observations and evidence for pass, fail, not applicable or unverified.",
        "Use temporary fixtures for action tests. After an authorized installation, verify the actual host separately.", "",
        "## Automatic findings", "",
    ]
    lines += [f"- {marks[level]} {message}" for level, message in findings]
    lines += ["", "## Pictures", ""]
    lines += [f"- {label}: `{path.name}`" for label, path in pictures]
    lines += ["", "## Review record (complete after observation)", "",
              "| Check | Outcome | Evidence / limitation |", "|---|---|---|",
              "| Visual match to brief | unverified | Open the collected images |",
              "| Interaction and failure recovery | unverified | Exercise safe fixtures |",
              "| Motion and resource use | unverified | Observe playback and measure on target device |",
              "| Real host / input / translation | unverified | Requires the actual target host |",
              "", "## Checklist", "", checklist(env.SKILL_ROOT) or "See references/quality-review.md."]
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps({"theme": theme_id, "coverage": coverage, "evidence": evidence,
        "findings": findings, "cases": cases, "measured": measured, "pictures": [str(p) for _, p in pictures]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return worst, report_path
