"""Render the RecallOS app icon (256x256 RGBA PNG) with no image libraries.

Midnight rounded square, vertical electric-blue light beams, a cantaloupe "memory orb" glowing on the horizon.
Run:  python make_icon.py  ->  icon.png
"""
import math
import pathlib
import struct
import zlib

S = 256
MID = (2, 7, 10)
BLUE = (2, 151, 222)
ORANGE = (252, 115, 77)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def clamp(v):
    return max(0, min(255, int(round(v))))


def pixel(x, y):
    # rounded-square mask (radius 56) with 1.5px antialias
    r = 56
    cx = min(max(x, r), S - 1 - r)
    cy = min(max(y, r), S - 1 - r)
    d = math.hypot(x - cx, y - cy)
    alpha = max(0.0, min(1.0, (r - d) + 0.5))
    if alpha <= 0:
        return (0, 0, 0, 0)
    v = y / S
    col = mix(MID, (6, 40, 70), v ** 1.6)  # midnight -> deep blue toward the bottom
    # vertical beams, brighter near the horizon
    beam = 0.0
    for bx in (60, 92, 128, 164, 196):
        beam += math.exp(-((x - bx) ** 2) / 18.0)
    beam *= max(0.0, v - 0.15) ** 1.4 * 0.9
    col = mix(col, (95, 196, 242), min(1.0, beam))
    # horizon glow + orb
    ox, oy = 128, 176
    od = math.hypot(x - ox, y - oy)
    glow = math.exp(-((od / 70.0) ** 2)) * 0.75
    col = mix(col, ORANGE, glow)
    core = max(0.0, 1 - od / 34.0)
    if core > 0:
        orb = mix(ORANGE, (255, 222, 205), max(0.0, 1 - math.hypot(x - ox, y - (oy - 10)) / 26.0))
        col = mix(col, orb, min(1.0, core * 3.0))
    # thin electric-blue rim
    rim = max(0.0, 1 - abs(d - (r - 3)) / 2.0) if d > r - 6 else 0.0
    edge = x < r or x > S - 1 - r or y < r or y > S - 1 - r
    if not edge:
        rim = max(rim, max(0.0, 1 - min(x, y, S - 1 - x, S - 1 - y) / 3.0))
    col = mix(col, BLUE, rim * 0.8)
    return (clamp(col[0]), clamp(col[1]), clamp(col[2]), clamp(alpha * 255))


def write_png(path, w, h, px):
    raw = b"".join(b"\x00" + b"".join(struct.pack("BBBB", *px(x, y)) for x in range(w)) for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    pathlib.Path(path).write_bytes(png)


if __name__ == "__main__":
    out = pathlib.Path(__file__).with_name("icon.png")
    write_png(out, S, S, pixel)
    print("wrote", out)
