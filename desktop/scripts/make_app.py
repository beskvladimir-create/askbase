#!/usr/bin/env python3
"""Build a minimal Askbase.app so macOS knows the application by name.

    python scripts/make_app.py

Without a bundle the menu bar, the Dock and the application switcher all call
it "python" with a rocket icon, and the window is genuinely hard to find among
other windows. That is not cosmetic: it is why the application looked as though
it had not started.

This is not the shipping build. It points at the development environment rather
than carrying its own, so it only runs on this machine. Signing, notarisation
and a .dmg come later.
"""
from __future__ import annotations

import plistlib
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "build" / "Askbase.app"
PYTHON = ROOT / ".venv" / "bin" / "python"

PLIST = {
    "CFBundleName": "Askbase",
    "CFBundleDisplayName": "Askbase",
    "CFBundleIdentifier": "tech.besk.askbase",
    "CFBundleVersion": "0.1.1",
    "CFBundleShortVersionString": "0.1.1",
    "CFBundlePackageType": "APPL",
    "CFBundleExecutable": "askbase",
    "CFBundleIconFile": "icon.icns",
    "NSHighResolutionCapable": True,
    # The application reads databases the user points it at; macOS asks about
    # protected folders, and the string explains why before it asks.
    "NSDesktopFolderUsageDescription": "Чтобы открыть базу данных, которую вы выберете.",
    "NSDocumentsFolderUsageDescription": "Чтобы открыть базу данных, которую вы выберете.",
    "NSDownloadsFolderUsageDescription": "Чтобы открыть базу данных, которую вы выберете.",
    "LSMinimumSystemVersion": "13.0",
    "LSApplicationCategoryType": "public.app-category.productivity",
}

LAUNCHER = f"""#!/bin/sh
# Development bundle: runs the package from the working tree. Launched from
# Finder the working directory is "/", so the package directory has to be put
# on the path explicitly or the import fails and nothing appears at all.
export PYTHONPATH="{ROOT}"
cd "{ROOT}"
exec "{PYTHON}" -m askbase "$@"
"""


def main() -> None:
    if not PYTHON.exists():
        sys.exit(f"нет окружения: {PYTHON}. Сначала: uv venv && uv pip install PySide6 sqlglot")
    if APP.exists():
        shutil.rmtree(APP)
    macos = APP / "Contents" / "MacOS"
    resources = APP / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    (APP / "Contents" / "Info.plist").write_bytes(plistlib.dumps(PLIST))
    launcher = macos / "askbase"
    launcher.write_text(LAUNCHER, encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    shutil.copy2(ROOT / "askbase" / "icon.icns", resources / "icon.icns")

    print(f"собрано: {APP}")
    print("открыть:  open", APP)
    print("положить в программы:  ln -sf", APP, "/Applications/Askbase.app")


if __name__ == "__main__":
    main()
