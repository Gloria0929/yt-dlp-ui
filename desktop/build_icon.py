#!/usr/bin/env python3
"""生成 FRAME/GET 桌面应用图标（macOS .icns + 通用 PNG）。

用法: python3 desktop/build_icon.py
产物: build/icon.icns, build/icon.png（1024x1024）

图标沿用网页品牌标记的三根条形，纸张配色在浅色与深色 Dock 中都保持辨识度。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ICONSET = BUILD / "icon.iconset"

INK = (24, 35, 33, 255)
CREAM = (241, 237, 227, 255)
ACCENT = (233, 94, 63, 255)
SS = 4  # 超采样倍数，保证圆角与条形边缘平滑


def render(size: int) -> Image.Image:
    """macOS 风格圆角方形图标：四周留白 9%，底部投影，条形比例对齐 .brand-mark。"""
    canvas = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    pad = round(size * 0.09) * SS
    box = size * SS - pad * 2
    radius = round(box * 0.235)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (pad, pad + round(size * 0.022) * SS, pad + box, pad + box + round(size * 0.022) * SS),
        radius=radius,
        fill=(0, 0, 0, 90),
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size * 0.018 * SS)))

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((pad, pad, pad + box, pad + box), radius=radius, fill=INK)

    bars = ((1.0, CREAM), (0.62, CREAM), (0.34, ACCENT))
    gap = box * 0.085
    bar_w = (box * 0.52 - gap * 2) / 3
    left = pad + box * 0.24
    base = pad + box * 0.76
    top = pad + box * 0.245
    bar_radius = max(round(bar_w * 0.16), 1)
    for index, (ratio, color) in enumerate(bars):
        x0 = left + index * (bar_w + gap)
        y0 = base - (base - top) * ratio
        draw.rounded_rectangle(
            (round(x0), round(y0), round(x0 + bar_w), round(base)),
            radius=bar_radius,
            fill=color,
        )
    return canvas.resize((size, size), Image.LANCZOS)


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    render(1024).save(BUILD / "icon.png")

    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir(parents=True)
    for base in (16, 32, 128, 256, 512):
        render(base).save(ICONSET / f"icon_{base}x{base}.png")
        render(base * 2).save(ICONSET / f"icon_{base}x{base}@2x.png")
    if sys.platform == "darwin":
        subprocess.run(
            ["iconutil", "-c", "icns", str(ICONSET), "-o", str(BUILD / "icon.icns")],
            check=True,
        )
    shutil.rmtree(ICONSET, ignore_errors=True)
    print(f"icon.png + icon.icns -> {BUILD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
