"""Bundle web fonts into a theme, so it looks the same offline and where Google Fonts is blocked.

A theme that loads its fonts from fonts.googleapis.com falls back to whatever the system has when
the network says no (in mainland China, behind some proxies, at sign-in before Wi-Fi). On Windows
that is often SimSun or Times New Roman, and the desktop suddenly looks cheap. This module asks
Google Fonts for subsets that contain only the characters the theme needs (the CSS2 `text=`
parameter), saves the WOFF2 files in the theme's assets/fonts folder and writes a fonts.css with
matching unicode-range rules, so the browser downloads nothing at run time.

Chinese is large, so the common set is opt-in: `common-zh` adds the 3,755 level-1 GB2312 characters
(all everyday Simplified Chinese) plus CJK punctuation, which is enough for user input such as a
search box or a prayer. Everything else in the theme (its own labels) is always included.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

CSS_API = "https://fonts.googleapis.com/css2"
# Google Fonts picks the file format from the browser; ask as a current Chrome so we get WOFF2.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CHUNK = 600            # characters per request: keeps the URL well under Google's limit
TEXT_SUFFIXES = {".html", ".htm", ".js", ".css", ".json", ".svg", ".txt"}
CJK_PUNCTUATION = "，。、；：？！“”‘’（）《》〈〉【】「」『』—…·～　"


def common_zh() -> str:
    """The 3,755 level-1 GB2312 characters, decoded from their code points (no data file needed)."""
    chars = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            if hi == 0xD7 and lo > 0xF9:
                break
            try:
                chars.append(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    return "".join(chars) + CJK_PUNCTUATION


def theme_text(folder: Path) -> str:
    """Every character used in the theme's own files (labels, scripts, manifest)."""
    seen = set()
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and "fonts" not in path.parts:
            try:
                seen.update(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "".join(sorted(ch for ch in seen if ch.isprintable() and not ch.isspace()))


def ascii_text() -> str:
    return "".join(chr(c) for c in range(0x20, 0x7F)) + "·—–‘’“”…°×"


def _ranges(chars: Iterable[str]) -> str:
    points = sorted({ord(ch) for ch in chars})
    out: List[str] = []
    start = prev = None
    for p in points:
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(f"U+{start:X}" if start == prev else f"U+{start:X}-{prev:X}")
            start = prev = p
    if start is not None:
        out.append(f"U+{start:X}" if start == prev else f"U+{start:X}-{prev:X}")
    return ", ".join(out)


def _get(url: str, timeout: float = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # system proxy settings apply
        return response.read()


def _fetch_subset(family: str, weight: int, italic: bool, text: str) -> bytes:
    axis = f"ital,wght@1,{weight}" if italic else f"wght@{weight}"
    query = urllib.parse.urlencode({"family": f"{family}:{axis}", "text": text, "display": "block"})
    css = _get(f"{CSS_API}?{query}").decode("utf-8", errors="replace")
    match = re.search(r"url\((https://[^)]+)\)\s*format\('woff2'\)", css)
    if not match:
        raise RuntimeError(f"Google Fonts returned no WOFF2 for {family} {weight}")
    return _get(match.group(1))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def bundle(
    theme_dir: Path,
    family: str,
    weights: List[int],
    *,
    name: Optional[str] = None,
    italic: bool = False,
    chars: str = "",
    log=print,
) -> Tuple[Path, List[Path]]:
    """Download subsets of `family` covering `chars`, write them and update assets/fonts/fonts.css.

    `name` is the font-family name the theme will use (default: the Google family name). Using a
    theme-specific name avoids clashing with a different version installed on the computer.
    """
    out_dir = theme_dir / "assets" / "fonts"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = name or family
    unique = "".join(sorted(set(chars)))
    chunks = [unique[i:i + CHUNK] for i in range(0, len(unique), CHUNK)] or [ascii_text()]
    written: List[Path] = []
    faces: List[str] = []
    for weight in weights:
        for index, chunk in enumerate(chunks):
            data = _fetch_subset(family, weight, italic, chunk)
            file = out_dir / f"{slug(name)}-{weight}{'i' if italic else ''}-{index}.woff2"
            file.write_bytes(data)
            written.append(file)
            faces.append(
                "@font-face {\n"
                f"  font-family: \"{name}\";\n"
                f"  font-style: {'italic' if italic else 'normal'};\n"
                f"  font-weight: {weight};\n"
                "  font-display: block;\n"
                f"  src: url(\"{file.name}\") format(\"woff2\");\n"
                f"  unicode-range: {_ranges(chunk)};\n"
                "}\n"
            )
            log(f"  {file.name}  {len(chunk)} characters  {len(data) // 1024} KB")
    css_path = out_dir / "fonts.css"
    existing = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    block = ""
    for weight in weights:      # one marked block per weight, so bundling another weight later keeps this one
        label = f"{name} {weight} {'italic' if italic else 'normal'}"
        marker_start, marker_end = f"/* {label} — start */\n", f"/* {label} — end */\n"
        existing = re.sub(re.escape(marker_start) + r".*?" + re.escape(marker_end), "", existing, flags=re.S)
        block += marker_start + "".join(f for f in faces if f"font-weight: {weight};" in f) + marker_end
    header = "" if existing.strip() else (
        "/* Fonts bundled with orbit.py fonts: subsets downloaded from Google Fonts (licenses in LICENSE.txt).\n"
        "   Load with <link rel=\"stylesheet\" href=\"assets/fonts/fonts.css\"> before style.css. */\n"
    )
    css_path.write_text(header + existing + block, encoding="utf-8")
    licence = out_dir / "LICENSE.txt"
    note = (f"{family}: from Google Fonts; license on https://fonts.google.com/specimen/{family.replace(' ', '+')}/license "
            "(most families use the SIL Open Font License 1.1)\n")
    previous = licence.read_text(encoding="utf-8") if licence.exists() else ""
    if note not in previous:
        licence.write_text(previous + note, encoding="utf-8")
    return css_path, written


def plan_chars(theme_dir: Path, sets: List[str]) -> str:
    """Characters for a bundle: the theme's own text plus any named sets (common-zh, ascii)."""
    text = theme_text(theme_dir) + ascii_text()
    for item in sets:
        if item == "common-zh":
            text += common_zh()
        elif item == "ascii":
            text += ascii_text()
        elif item and item != "theme":
            text += item          # literal extra characters
    return text


def describe(paths: List[Path]) -> Dict[str, int]:
    return {p.name: p.stat().st_size for p in paths}
