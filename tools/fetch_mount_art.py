#!/usr/bin/env python3
"""Fill `assets/mounts/` with the FFXI Wiki picture of every mount.

The Mount HUD wants one square picture per mount, and the client renders mounts without a way
to frame them consistently.  The FFXI Wiki's Category:Mounts page has a screenshot for each of
the 39 mounts, so this tool reads that page, matches its entries to the client's mount names,
and writes `assets/mounts/<id>.jpg` (and, unless --no-install, `<data>/mounts/<id>.jpg` for the
running client).

The pictures are FINAL FANTASY XI artwork from the FFXI Wiki (bg-wiki.com), © SQUARE ENIX.  They
are used here as reference art for a fan project; see THIRD_PARTY_NOTICES.md.

    tools/fetch_mount_art.py
    tools/fetch_mount_art.py --no-install --ids 0,5,24
    tools/fetch_mount_art.py --size 320

Re-run it when a client update adds mounts; the names are matched to
`server/fanxi_server/game/mounts.py`, which is generated from the client's own table.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - development machines only
    print("Pillow is needed: python3 -m pip install pillow", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.game import mounts  # noqa: E402

CATEGORY = "https://www.bg-wiki.com/ffxi/Category:Mounts"
DEFAULT_DATA = Path.home() / "Library" / "Application Support" / "Fanxi" / "FFXI"
USER_AGENT = "fanxi-mount-art/1.0 (+https://github.com/; fan project asset fetch)"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def fold(text: str) -> str:
    """A wiki entry name as a lookup key: no ♪, companion/whistle/key, case or spacing."""
    text = text.replace("♪", "")
    for suffix in (" companion", " whistle", " key"):
        if text.casefold().endswith(suffix):
            text = text[: -len(suffix)]
            break
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.casefold()).split())


def category_images(html: str) -> dict[str, str]:
    """Companion entry name -> its picture's URL, from the Category:Mounts tables."""
    entries: dict[str, str] = {}
    for match in re.finditer(r'<th colspan="3">\s*<a href="/ffxi/([^"]+)" title="([^"]+)">([^<]+)</a>',
                             html):
        name = match.group(3).strip()
        tail = html[match.end():match.end() + 4000]
        image = re.search(r'<img[^>]+src="([^"]+)"', tail)
        if image:
            entries[fold(name)] = image.group(1)
    return entries


def original_url(src: str) -> str:
    """The full-size file behind a MediaWiki thumbnail (or the src when it is not one)."""
    match = re.match(r"(/images)/thumb/([0-9a-f])/([0-9a-f]{2})/([^/]+)/[^/]+$", src)
    if match:
        return "https://www.bg-wiki.com%s/%s/%s/%s" % (
            match.group(1), match.group(2), match.group(3), match.group(4))
    return "https://www.bg-wiki.com" + src


def square(image: Image.Image, size: int) -> Image.Image:
    """The whole picture, centred on the HUD's dark card colour.

    A few mounts only have their item icon on the wiki, drawn on a flat white page.  A white
    background is keyed out so the icon sits on the card instead of in a white box.
    """
    image = image.convert("RGBA")
    width, height = image.size
    corners = [image.getpixel((0, 0)), image.getpixel((width - 1, 0)),
               image.getpixel((0, height - 1)), image.getpixel((width - 1, height - 1))]
    if all(min(pixel[:3]) >= 235 for pixel in corners):
        pixels = image.load()
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                if r >= 235 and g >= 235 and b >= 235:
                    pixels[x, y] = (r, g, b, 0)
    canvas = Image.new("RGBA", (size, size), (12, 14, 18, 255))
    fitted = ImageOps.contain(image, (size, size), Image.LANCZOS)
    canvas.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return canvas.convert("RGB")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "assets" / "mounts")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="client data folder to install into")
    parser.add_argument("--no-install", action="store_true")
    parser.add_argument("--ids", default="", help="only these mount ids (default: all)")
    parser.add_argument("--size", type=int, default=256)
    args = parser.parse_args(argv)

    print("reading", CATEGORY)
    entries = category_images(fetch(CATEGORY).decode("utf-8", "replace"))
    if not entries:
        print("no mount pictures found on the category page", file=sys.stderr)
        return 2
    print("%d wiki entries" % len(entries))

    wanted = [int(part) for part in args.ids.split(",") if part.strip()] if args.ids else None
    args.out.mkdir(parents=True, exist_ok=True)
    install = None
    if not args.no_install:
        install = args.data / "mounts"
        install.mkdir(parents=True, exist_ok=True)

    missing, written = [], 0
    for mount in mounts.all_mounts():
        if wanted is not None and int(mount.id) not in wanted:
            continue
        src = entries.get(fold(mount.name))
        if not src:
            missing.append(mount.name)
            print("  %2d %-16s no wiki entry" % (mount.id, mount.name), file=sys.stderr)
            continue
        try:
            data = fetch(original_url(src))
            image = Image.open(io.BytesIO(data))
            picture = square(image, args.size)
        except Exception as exc:
            missing.append(mount.name)
            print("  %2d %-16s failed: %s" % (mount.id, mount.name, exc), file=sys.stderr)
            continue
        target = args.out / ("%d.jpg" % mount.id)
        picture.save(target, "JPEG", quality=92, optimize=True)
        if install is not None:
            picture.save(install / ("%d.jpg" % mount.id), "JPEG", quality=92, optimize=True)
        written += 1
        print("  %2d %-16s %s" % (mount.id, mount.name, target))

    print("%d picture(s) written, %d missing" % (written, len(missing)))
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
