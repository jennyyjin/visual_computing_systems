"""
Read and write simple binary PPM image frames without extra dependencies.
"""

from __future__ import annotations

from pathlib import Path


def write_ppm(path: Path, width: int, height: int, pixels: bytes) -> None:
    expected = width * height * 3
    if len(pixels) != expected:
        raise ValueError(f"expected {expected} RGB bytes, got {len(pixels)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        f.write(pixels)


def read_ppm(path: Path) -> tuple[int, int, bytes]:
    with path.open("rb") as f:
        magic = f.readline().strip()
        if magic != b"P6":
            raise ValueError(f"{path} is not a binary PPM file")

        line = f.readline()
        while line.startswith(b"#"):
            line = f.readline()
        width_s, height_s = line.split()
        width = int(width_s)
        height = int(height_s)

        max_value = int(f.readline().strip())
        if max_value != 255:
            raise ValueError(f"{path} has unsupported max value {max_value}")

        pixels = f.read()

    expected = width * height * 3
    if len(pixels) != expected:
        raise ValueError(f"{path} has {len(pixels)} RGB bytes, expected {expected}")
    return width, height, pixels
