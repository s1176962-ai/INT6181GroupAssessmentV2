"""Create soft subject placeholder PNGs with the stdlib only."""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "images"


def png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    red, green, blue = rgb
    raw = b"".join(b"\x00" + bytes([red, green, blue]) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    (OUT / "subjects").mkdir(parents=True, exist_ok=True)
    (OUT / "questions").mkdir(parents=True, exist_ok=True)
    png(OUT / "placeholder.png", 320, 180, (236, 232, 223))
    png(OUT / "subjects" / "english.png", 320, 180, (231, 244, 234))
    png(OUT / "subjects" / "mathematics.png", 320, 180, (232, 238, 244))
    png(OUT / "subjects" / "science.png", 320, 180, (247, 236, 214))
    print("wrote", list(OUT.rglob("*.png")))


if __name__ == "__main__":
    main()
