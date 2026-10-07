#!/bin/sh
# Orbit Desktop - double-click to start on macOS.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  exec python3 runtime/orbit.py quickstart
fi
echo "Orbit Desktop needs Python 3.9 or newer."
echo "Install it from https://www.python.org/downloads/ (or run: xcode-select --install), then try again."
echo "Orbit Desktop 需要 Python 3.9 或更新版本。请从 python.org 安装后再双击本文件。"
read -r _
