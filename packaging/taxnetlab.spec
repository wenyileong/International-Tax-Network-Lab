# PyInstaller specification for the single-file executable (plan v2.1, s 4.4).
# Build from the repository root:  pyinstaller --noconfirm --clean packaging/taxnetlab.spec
# Run scripts/write_build_manifest.py first so that the build manifest is bundled.

import os
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
PKG = ROOT / "src" / "taxnetlab"

datas = [
    (str(PKG / "web" / "index.html"), "taxnetlab/web"),
    (str(PKG / "web" / "app.css"), "taxnetlab/web"),
    (str(PKG / "web" / "app.js"), "taxnetlab/web"),
    (str(PKG / "web" / "icon.svg"), "taxnetlab/web"),
    (str(PKG / "web" / "vendor" / "plotly.min.js"), "taxnetlab/web/vendor"),
]
datas += [(str(p), "taxnetlab/web/locales") for p in sorted((PKG / "web" / "locales").glob("*.json"))]
datas += [(str(p), "taxnetlab/data") for p in sorted((PKG / "data").glob("*.json"))]
datas += [(str(p), "taxnetlab/guide") for p in sorted((PKG / "guide").glob("*.md"))]
# The Research Suite core (vendored, see scripts/sync_rscore.py): its registry data and provenance record.
RS = ROOT / "src" / "rscore"
datas += [(str(p), "rscore/data") for p in sorted((RS / "data").glob("*.json"))]
datas.append((str(RS / "VENDORED.json"), "rscore"))
if (PKG / "_build_manifest.json").exists():
    datas.append((str(PKG / "_build_manifest.json"), "taxnetlab"))

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=["rscore", "rscore.services", "rscore.importers.ashare"],
    excludes=["tkinter", "numpy", "scipy", "pandas", "matplotlib", "IPython", "pytest", "hypothesis", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="taxnetlab",
    console=True,  # the console window shows the address and stops the server when closed
    upx=False,     # UPX packing raises antivirus false positives (plan s 12)
    debug=False,
    strip=False,
    runtime_tmpdir=None,
    icon=str(ROOT / "packaging" / "taxnetlab.ico"),
)
