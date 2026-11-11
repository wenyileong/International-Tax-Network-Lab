"""Copy the Research Suite core (``rscore``) into this repository, pinned to a commit.

The Lab uses the suite's shared core for importing A-share Company Intelligence releases, so that the Lab
and ResearchSuite.exe convert the same release in exactly the same way (one converter, not two). The copy
is never edited here: change the core in ``wenyileong/research-suite-core`` and sync again.

    python scripts/sync_rscore.py PATH_TO_research-suite-core

Writes ``src/rscore/`` and ``src/rscore/VENDORED.json`` (source commit and the SHA-256 of every file).
``tests/test_ashare_import.py`` fails if any vendored file differs from the recorded hash.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src" / "rscore"
FILES = ("__init__.py", "canonical.py", "conventions.py", "schema.py", "store.py", "validation.py",
         "jurisdictions.py", "places.py", "export.py", "snapshot.py", "services.py", "demo.py",
         "importers/__init__.py", "importers/ashare.py", "data/iso3166.json", "data/place_aliases.json")


def main(src_repo: str) -> None:
    src = Path(src_repo).resolve() / "src" / "rscore"
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    if DEST.exists():
        shutil.rmtree(DEST)
    hashes = {}
    for rel in FILES:
        target = DEST / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, target)
        hashes[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
    (DEST / "VENDORED.json").write_text(json.dumps({
        "source": "https://github.com/wenyileong/research-suite-core", "commit": commit,
        "note": "Copied by scripts/sync_rscore.py; do not edit here.", "files": hashes}, indent=2) + "\n",
        encoding="utf-8")
    print(f"vendored rscore at {commit[:7]}: {len(FILES)} files")


if __name__ == "__main__":
    main(sys.argv[1])
