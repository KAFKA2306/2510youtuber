#!/usr/bin/env python3
"""A lightweight stand-in for ffmpeg used during unit tests.

The script understands the two command shapes exercised by the test-suite:
1. Generating a synthetic video via ``-f lavfi -i testsrc``.  We simply
   create an empty placeholder file at the requested output location.
2. Extracting PNG screenshots via ``-filter:v fps=...`` and ``-vframes``.
   Instead of decoding real video we materialize solid-colour 1x1 PNG files
   that satisfy the downstream assertions.
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path
from typing import List, Optional

# A tiny 1x1px PNG image (opaque white) encoded in base64 to avoid binary blobs
# inside the repository.
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)


def _write_placeholder_video(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"mock video")


def _substitute_frame(pattern: str, index: int) -> str:
    def repl(match: re.Match[str]) -> str:
        width = match.group(1)
        if width:
            return f"{index:0{int(width)}d}"
        return str(index)

    return re.sub(r"%0?(\d*)d", repl, pattern)


def _write_placeholder_frames(pattern: str, count: int) -> None:
    for idx in range(1, count + 1):
        target = Path(_substitute_frame(pattern, idx))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_PNG_BYTES)


def _extract_output(argv: List[str]) -> Optional[Path]:
    for token in reversed(argv):
        if token == "-y":
            continue
        if token.startswith("-"):
            continue
        return Path(token)
    return None


def main(argv: List[str]) -> int:
    if not argv:
        return 1

    output = _extract_output(argv)
    if output is None:
        return 1

    if "%" in output.as_posix():
        try:
            frames_idx = argv.index("-vframes") + 1
            frame_count = int(argv[frames_idx])
        except (ValueError, IndexError):
            frame_count = 1
        _write_placeholder_frames(output.as_posix(), frame_count)
        return 0

    _write_placeholder_video(output)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
