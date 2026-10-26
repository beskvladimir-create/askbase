#!/usr/bin/env python3
"""Pack the built application into a .dmg for download.

    python scripts/make_dmg.py

The build is not signed with an Apple developer certificate, so macOS will
refuse to open it until the person allows it once by hand. The site says so
plainly next to the link rather than letting them hit the wall first.
"""
from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dist" / "Askbase.app"


def main() -> None:
    if not APP.exists():
        sys.exit(f"нет сборки: {APP}. Сначала: pyinstaller askbase.spec --noconfirm")
    version = plistlib.loads((APP / "Contents" / "Info.plist").read_bytes())["CFBundleShortVersionString"]
    out = ROOT / "dist" / f"Askbase-{version}-macos-arm64.dmg"
    out.unlink(missing_ok=True)

    staging = ROOT / "dist" / "dmg"
    subprocess.run(["rm", "-rf", str(staging)], check=True)
    staging.mkdir(parents=True)
    subprocess.run(["cp", "-R", str(APP), str(staging / "Askbase.app")], check=True)
    # The drop target, so the window explains itself without a background image.
    (staging / "Applications").symlink_to("/Applications")

    subprocess.run([
        "hdiutil", "create", "-volname", "Askbase", "-srcfolder", str(staging),
        "-ov", "-format", "UDZO", str(out),
    ], check=True, capture_output=True)
    subprocess.run(["rm", "-rf", str(staging)], check=True)

    size = out.stat().st_size / 1_048_576
    sha = subprocess.run(["shasum", "-a", "256", str(out)],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    print(f"{out.name}  {size:.0f} МБ")
    print(f"SHA-256  {sha}")
    print("не подписано: Gatekeeper откажет, пока пользователь не разрешит вручную")


if __name__ == "__main__":
    main()
