"""Exports Narcisse's icon for the installable app and the Start menu shortcut.

    uv run python scripts/make-icons.py

The icon is drawn in `src/narcisse/desktop/art.py`; run this again after changing it.
"""

from pathlib import Path

from narcisse.desktop.art import flower

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"

for size in (192, 512):
    flower(size, background=True).save(PUBLIC / f"icon-{size}.png", optimize=True)
# Maskable: the system crops it to its own shape, so the flower keeps to the safe centre.
flower(512, background=True, padding=0.2).save(PUBLIC / "icon-maskable-512.png", optimize=True)
flower(180, background=True).save(PUBLIC / "apple-touch-icon.png", optimize=True)
flower(256, background=True).save(
    ROOT / "src" / "narcisse" / "desktop" / "narcisse.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("icons written")
