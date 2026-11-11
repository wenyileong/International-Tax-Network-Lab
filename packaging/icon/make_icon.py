"""Draw the International Tax Network Lab icon and write it in every format the build needs.

Design, in the family of the Research Suite icon (same indigo rounded square, same flat style): a small
network of four jurisdictions. The direct link from the home jurisdiction (lower left) to the host
(upper right) is dashed; the cheapest route, which runs through a conduit (upper left), is drawn thick in
the suite's green, the colour the suite uses for networks and for the Lab. The fourth jurisdiction, on a
route that is not taken, is hollow. At 16 to 48 pixels the thin links and the dashes are left out, so the
green route and its three nodes stay legible.

Run from the repository root (Pillow is a development-only dependency):

    python packaging/icon/make_icon.py

Outputs (committed, so that a build does not need Pillow):
    packaging/icon/taxnetlab.svg        editable source of the design
    packaging/taxnetlab.ico             Windows icon, 16 to 256 px (executable, installer, shortcuts)
    src/taxnetlab/web/icon.svg          favicon and top-bar logo of the interface
    docs/images/icon_256.png            for the README and release pages
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SIZE = 1024
SUPERSAMPLE = 4

BACKGROUND = "#4338CA"
WHITE = "#FFFFFF"
ROUTE = "#10B981"
CORNER = 220

HOME, CONDUIT, HOST, OTHER = (262, 762), (262, 290), (762, 290), (762, 762)
THIN, ROUTE_W, DASH = 30, 92, (64, 46)
NODE, RING = 112, 34
SMALL = {"route": 150, "node": 176, "ring": 52}


def _dashes(a, b, on, off):
    (x1, y1), (x2, y2) = a, b
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    span = length - 2 * (NODE + 40)
    n = int((span + off) // (on + off))
    pos = NODE + 40 + (span - (n * on + (n - 1) * off)) / 2  # centred between the two nodes
    for _ in range(n):
        yield (x1 + ux * pos, y1 + uy * pos), (x1 + ux * (pos + on), y1 + uy * (pos + on))
        pos += on + off


def _draw(px: int, small: bool) -> Image.Image:
    s = px * SUPERSAMPLE / SIZE
    img = Image.new("RGBA", (px * SUPERSAMPLE,) * 2, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, SIZE * s - 1, SIZE * s - 1], radius=CORNER * s, fill=BACKGROUND)
    sc = lambda p: (p[0] * s, p[1] * s)  # noqa: E731
    if not small:
        for a, b in ((HOME, OTHER), (OTHER, HOST)):
            d.line([sc(a), sc(b)], fill=WHITE, width=round(THIN * s))
        for p, q in _dashes(HOME, HOST, *DASH):
            d.line([sc(p), sc(q)], fill=WHITE, width=round(THIN * s))
    width = (SMALL["route"] if small else ROUTE_W) * s
    d.line([sc(HOME), sc(CONDUIT), sc(HOST)], fill=ROUTE, width=round(width), joint="curve")
    r = width / 2
    d.ellipse([CONDUIT[0] * s - r, CONDUIT[1] * s - r, CONDUIT[0] * s + r, CONDUIT[1] * s + r], fill=ROUTE)
    node, ring = (SMALL["node"], SMALL["ring"]) if small else (NODE, RING)
    for p, colour in ((HOME, ROUTE), (CONDUIT, ROUTE), (HOST, ROUTE), (OTHER, BACKGROUND)):
        if small and p == OTHER:
            continue
        x, y = p
        r = node * s
        d.ellipse([x * s - r, y * s - r, x * s + r, y * s + r], fill=WHITE)
        r = (node - ring) * s
        d.ellipse([x * s - r, y * s - r, x * s + r, y * s + r], fill=colour)
    return img.resize((px, px), Image.LANCZOS)


def icon(px: int) -> Image.Image:
    return _draw(px, small=px <= 48)


def svg() -> str:
    dashes = "".join(f'<line x1="{p[0]:.0f}" y1="{p[1]:.0f}" x2="{q[0]:.0f}" y2="{q[1]:.0f}"/>' for p, q in _dashes(HOME, HOST, *DASH))
    thin = "".join(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}"/>' for a, b in ((HOME, OTHER), (OTHER, HOST)))
    nodes = "".join(f'<circle cx="{x}" cy="{y}" r="{NODE}" fill="{WHITE}"/><circle cx="{x}" cy="{y}" r="{NODE - RING}" fill="{c}"/>'
                    for (x, y), c in ((HOME, ROUTE), (CONDUIT, ROUTE), (HOST, ROUTE), (OTHER, BACKGROUND)))
    route = f"M{HOME[0]} {HOME[1]}L{CONDUIT[0]} {CONDUIT[1]}L{HOST[0]} {HOST[1]}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}">'
            f'<title>International Tax Network Lab</title>'
            f'<rect width="{SIZE}" height="{SIZE}" rx="{CORNER}" fill="{BACKGROUND}"/>'
            f'<g stroke="{WHITE}" stroke-width="{THIN}" stroke-linecap="butt">{thin}{dashes}</g>'
            f'<path d="{route}" fill="none" stroke="{ROUTE}" stroke-width="{ROUTE_W}" stroke-linejoin="round" stroke-linecap="round"/>'
            f'{nodes}</svg>\n')


def main() -> None:
    (ROOT / "packaging" / "icon").mkdir(parents=True, exist_ok=True)
    text = svg()
    (ROOT / "packaging" / "icon" / "taxnetlab.svg").write_text(text, encoding="utf-8")
    (ROOT / "src" / "taxnetlab" / "web" / "icon.svg").write_text(text, encoding="utf-8")
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    images = [icon(px) for px in sizes]
    images[-1].save(ROOT / "packaging" / "taxnetlab.ico", format="ICO", sizes=[(px, px) for px in sizes],
                    append_images=images[:-1])
    (ROOT / "docs" / "images").mkdir(parents=True, exist_ok=True)
    icon(256).save(ROOT / "docs" / "images" / "icon_256.png")
    print("wrote taxnetlab.svg, taxnetlab.ico, web/icon.svg, docs/images/icon_256.png")


if __name__ == "__main__":
    main()
