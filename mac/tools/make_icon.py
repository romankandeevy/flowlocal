"""Иконка FlowLocal по сетке иконок macOS: чёрный «сквиркл» 824 из 1024 с
тенью в самом рисунке, внутри - волна из семи капсул systemBlue. Тот же язык,
что у островка и окна: чёрное основание, один акцент.

    backend/.venv/bin/python tools/make_icon.py     ->  Resources/AppIcon.icns

Рисуем через поля расстояний (SDF): край сглаживается сам, без суперсэмплинга.
Нужен только numpy (он уже есть в окружении бэкенда); PNG пишется вручную,
.icns собирают системные sips и iconutil.
"""
import os
import shutil
import struct
import subprocess
import tempfile
import zlib

import numpy as np

N = 1024
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Resources", "AppIcon.icns")

y, x = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5


def squircle_sd(cx, cy, half, n=5.0):
    """Приближённое расстояние до суперэллипса |x|^n + |y|^n = half^n."""
    u = np.abs(x - cx) / half
    v = np.abs(y - cy) / half
    f = u ** n + v ** n - 1.0
    gx = n * u ** (n - 1) / half
    gy = n * v ** (n - 1) / half
    return f / np.maximum(np.hypot(gx, gy), 1e-6)


def capsule_sd(cx, top, bottom, r):
    """Расстояние до вертикальной капсулы радиуса r от top до bottom."""
    cy = np.clip(y, top + r, bottom - r)
    return np.hypot(x - cx, y - cy) - r


def cover(sd):
    """Доля пикселя внутри фигуры: сглаженный край шириной в пиксель."""
    return np.clip(0.5 - sd, 0.0, 1.0)


def over(dst, rgb, a):
    """Наложение слоя rgb с альфой a поверх dst (премультиплицированный RGBA)."""
    a = a[..., None]
    dst[..., :3] = np.asarray(rgb, np.float32) * a + dst[..., :3] * (1 - a)
    dst[..., 3:] = a + dst[..., 3:] * (1 - a)


def hexrgb(h):
    return np.array([(h >> 16) & 255, (h >> 8) & 255, h & 255], np.float32) / 255


img = np.zeros((N, N, 4), np.float32)
C, HALF = N / 2, 412.0          # сквиркл 824 x 824 в поле 1024

# Тень в рисунке, как у системных иконок: мягкая, чуть ниже.
shadow = squircle_sd(C, C + 14, HALF)
over(img, (0, 0, 0), 0.32 * np.clip(1 - shadow / 34, 0, 1) ** 2 * (shadow > -1))
over(img, (0, 0, 0), 0.18 * np.clip(1 - np.maximum(shadow, 0) / 10, 0, 1))

# Основание: почти чёрный, едва светлее сверху - объём без «градиента на фоне».
body = squircle_sd(C, C, HALF)
t = ((y - (C - HALF)) / (2 * HALF)).clip(0, 1)[..., None]
base = hexrgb(0x2A2A2E) * (1 - t) + hexrgb(0x0A0A0C) * t
over(img, base, cover(body))

# Тонкая кромка света по верхнему краю - так читается стекло корпуса.
rim = np.clip(1 - np.abs(body + 2.0) / 2.0, 0, 1) * np.clip((C - y) / HALF + 0.2, 0, 1)
over(img, (1, 1, 1), 0.16 * rim * cover(body))

# Волна: семь капсул systemBlue, выше к центру - голос, который становится текстом.
heights = [0.30, 0.55, 0.82, 1.0, 0.70, 0.46, 0.26]
bar_w, gap, full = 56.0, 30.0, 430.0
x0 = C - (len(heights) * bar_w + (len(heights) - 1) * gap) / 2 + bar_w / 2
top_col, bot_col = hexrgb(0x4DA3FF), hexrgb(0x0A6CFF)
for i, k in enumerate(heights):
    h = full * k
    sd = capsule_sd(x0 + i * (bar_w + gap), C - h / 2, C + h / 2, bar_w / 2)
    tt = ((y - (C - full / 2)) / full).clip(0, 1)[..., None]
    over(img, top_col * (1 - tt) + bot_col * tt, cover(sd))


def write_png(path, rgba):
    """RGBA 8 бит без фильтров: zlib и три чанка, больше PNG не нужно."""
    a = rgba[..., 3:4]
    rgb = np.where(a > 0, rgba[..., :3] / np.maximum(a, 1e-6), 0)
    px = (np.concatenate([rgb, a], axis=2).clip(0, 1) * 255 + 0.5).astype(np.uint8)
    raw = b"".join(b"\x00" + row.tobytes() for row in px)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    h, w = px.shape[:2]
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


tmp = tempfile.mkdtemp()
try:
    master = os.path.join(tmp, "icon_1024.png")
    write_png(master, img)
    iconset = os.path.join(tmp, "AppIcon.iconset")
    os.mkdir(iconset)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = size * scale
            name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(["sips", "-z", str(px), str(px), master, "--out", os.path.join(iconset, name)],
                           check=True, capture_output=True)
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", OUT], check=True)
    shutil.copy(master, os.path.join(HERE, "..", "build", "icon_1024.png")) if os.path.isdir(
        os.path.join(HERE, "..", "build")) else None
    print("готово:", os.path.normpath(OUT))
finally:
    shutil.rmtree(tmp)
