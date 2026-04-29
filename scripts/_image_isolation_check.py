#!/usr/bin/env python3
"""_image_isolation_check.py — image-budget contract self-check.

The skill contract: screenshots taken inside a forked subagent must NOT
leak as inline images into the parent chat's image budget. The actual
runtime test requires Claude to dispatch a Task subagent — this script
prepares fixtures + records the verification marker once Claude confirms
the test passed.

Usage:
    _image_isolation_check.py --gen-fixtures   # create 3 small PNGs for self-test
    _image_isolation_check.py --verify         # exit 0 if marker present, 1 otherwise
    _image_isolation_check.py --mark-verified  # write the marker after Claude confirms
    _image_isolation_check.py --status         # human-readable status
    _image_isolation_check.py --reset          # remove marker + fixtures (force re-test)
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import zlib
from pathlib import Path

# Windows stdout often defaults to cp1252; force UTF-8 so Cyrillic paths and
# em-dashes don't crash with UnicodeEncodeError. No-op on Linux/macOS.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

FIXTURE_NAMES = ("a.png", "b.png", "c.png")


def _skill_dir() -> Path:
    sd = os.environ.get("CLAUDE_SKILL_DIR")
    if sd:
        return Path(sd)
    return Path(__file__).resolve().parent.parent


def _fixtures_dir() -> Path:
    return _skill_dir() / "fixtures" / "iso-test"


def _marker_path() -> Path:
    return _skill_dir() / ".isolation-verified"


def _make_png(path: Path, color: tuple[int, int, int]) -> None:
    """Write a minimal valid 16x16 RGB PNG with a single solid color.

    Hand-rolled to avoid Pillow dependency. PNG layout: signature + IHDR + IDAT + IEND.
    """
    width = height = 16
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB, no filter, no interlace
    raw = b""
    row = b"\x00" + (bytes(color) * width)  # filter byte 0 + RGB pixels
    for _ in range(height):
        raw += row
    idat = zlib.compress(raw, 9)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.write_bytes(png)


def gen_fixtures() -> int:
    fdir = _fixtures_dir()
    fdir.mkdir(parents=True, exist_ok=True)
    colors = {
        "a.png": (220, 32, 32),    # red
        "b.png": (32, 200, 64),    # green
        "c.png": (32, 96, 220),    # blue
    }
    for name, color in colors.items():
        _make_png(fdir / name, color)
    print(f"[image_isolation_check] fixtures written to {fdir}")
    print("Next step: dispatch a Task subagent (general-purpose) with this prompt:")
    print("---")
    print("Read these 3 files with Read and return one short text description per file:")
    for name in FIXTURE_NAMES:
        print(f"  {fdir / name}")
    print("Output 3 lines, no preamble, no inline images.")
    print("---")
    print("If subagent returns 3 text lines without leaking images, run --mark-verified.")
    return 0


def verify() -> int:
    fdir = _fixtures_dir()
    missing = [n for n in FIXTURE_NAMES if not (fdir / n).is_file()]
    if missing:
        print(f"[image_isolation_check] FAIL — fixtures missing: {missing}")
        print("Run --gen-fixtures first.")
        return 1
    if not _marker_path().is_file():
        print("[image_isolation_check] FAIL — marker not present, isolation not yet verified")
        print(f"Marker path: {_marker_path()}")
        return 1
    print("[image_isolation_check] OK — isolation verified")
    return 0


def mark_verified() -> int:
    marker = _marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        "image-budget isolation verified by manual subagent self-test\n"
        "delete this file to force re-verification\n"
    )
    print(f"[image_isolation_check] marker written: {marker}")
    return 0


def status() -> int:
    fdir = _fixtures_dir()
    marker = _marker_path()
    print(f"Skill dir:       {_skill_dir()}")
    print(f"Fixtures dir:    {fdir}")
    print(f"Fixtures present:{all((fdir / n).is_file() for n in FIXTURE_NAMES)}")
    print(f"Marker:          {marker}")
    print(f"Marker present:  {marker.is_file()}")
    return 0


def reset() -> int:
    marker = _marker_path()
    if marker.is_file():
        marker.unlink()
        print(f"[image_isolation_check] removed {marker}")
    fdir = _fixtures_dir()
    for name in FIXTURE_NAMES:
        p = fdir / name
        if p.is_file():
            p.unlink()
            print(f"[image_isolation_check] removed {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--gen-fixtures", action="store_true")
    grp.add_argument("--verify", action="store_true")
    grp.add_argument("--mark-verified", action="store_true")
    grp.add_argument("--status", action="store_true")
    grp.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)

    if args.gen_fixtures:
        return gen_fixtures()
    if args.verify:
        return verify()
    if args.mark_verified:
        return mark_verified()
    if args.status:
        return status()
    if args.reset:
        return reset()
    parser.error("no action chosen")
    return 2


if __name__ == "__main__":
    sys.exit(main())
