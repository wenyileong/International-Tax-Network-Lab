"""Write src/taxnetlab/_build_manifest.json before packaging (plan v2.1, s 4.4).

Records the version, source commit (and whether the tree was modified), the lock-file hash and the
build time, so that the executable can report them and every run record carries them.

Usage: python scripts/write_build_manifest.py [LOCK_FILE]
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taxnetlab import __version__  # noqa: E402


def git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def main() -> int:
    lock = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "requirements" / "windows-build.lock"
    status = git("status", "--porcelain")
    manifest = {
        "version": __version__,
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "lock_file": lock.name if lock.exists() else None,
        "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None,
        "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "build_python": platform.python_version(),
        "build_platform": platform.platform(),
    }
    out = ROOT / "src" / "taxnetlab" / "_build_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
