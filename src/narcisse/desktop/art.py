"""Narcisse's icon, drawn rather than shipped: the tray shows it with a dot for the current state,
and `scripts/make-icons.py` exports it for the installable app and the Start menu shortcut."""

import math
from enum import StrEnum

from PIL import Image, ImageDraw

PETAL = (250, 247, 236, 255)
PETAL_EDGE = (150, 136, 96, 255)  # keeps the petals visible on a light taskbar
CORONA = (232, 163, 61, 255)
CORONA_DARK = (196, 120, 30, 255)
BACKGROUND = (28, 52, 42, 255)  # the dark green of the app's dark theme


class TrayState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"


DOTS = {
    TrayState.RUNNING: (56, 152, 236, 255),
    TrayState.PAUSED: (240, 180, 40, 255),
    TrayState.FAILED: (220, 50, 47, 255),
}

# Drawn at 4× then scaled down: Pillow's shapes are not antialiased.
SUPERSAMPLE = 4


def flower(size: int, *, background: bool = False, padding: float = 0.0) -> Image.Image:
    """The narcissus: six petals around a cup. `padding` keeps a margin (maskable icons)."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if background:
        draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big // 5, fill=BACKGROUND)
    center = big / 2
    reach = big / 2 * (1 - padding)
    length = reach * 0.95  # from the centre to the tip of a petal
    width = reach * 0.30  # half the width of a petal
    outline = max(1, big // 48)
    for i in range(6):
        angle = math.radians(i * 60 - 90)
        cos, sin = math.cos(angle), math.sin(angle)
        # A rotated ellipse, from the centre outwards.
        points = []
        for step in range(48):
            t = 2 * math.pi * step / 48
            along = length / 2 + math.cos(t) * length / 2
            across = math.sin(t) * width
            points.append(
                (center + along * cos - across * sin, center + along * sin + across * cos)
            )
        draw.polygon(points, fill=PETAL, outline=PETAL_EDGE, width=outline)
    cup = reach * 0.36
    draw.ellipse(
        (center - cup, center - cup, center + cup, center + cup),
        fill=CORONA,
        outline=CORONA_DARK,
        width=outline,
    )
    inner = cup * 0.45
    draw.ellipse((center - inner, center - inner, center + inner, center + inner), fill=CORONA_DARK)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def tray_icon(state: TrayState, size: int = 64) -> Image.Image:
    """The flower, with a coloured dot in the corner unless nothing is going on."""
    image = flower(size)
    dot = DOTS.get(state)
    if dot is None:
        return image
    big = Image.new("RGBA", (size * SUPERSAMPLE,) * 2, (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    radius = size * SUPERSAMPLE * 0.22
    cx = cy = size * SUPERSAMPLE - radius - 1
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=dot,
        outline=(255, 255, 255, 255),
        width=size * SUPERSAMPLE // 24,
    )
    overlay = big.resize((size, size), Image.Resampling.LANCZOS)
    return Image.alpha_composite(image, overlay)
