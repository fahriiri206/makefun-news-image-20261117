#!/usr/bin/env python3
"""make.fun entry: validate the committed entry.png and copy it to the output path."""

import hashlib
import os
import struct
import sys
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DIMENSION = 1024
MAX_BYTES = 1048576


class ValidationError(Exception):
    pass


def png_path():
    here = os.path.dirname(os.path.realpath(__file__))
    candidate = os.path.realpath(os.path.join(here, "entry.png"))
    if os.path.isfile(candidate):
        return candidate
    return os.path.realpath("/bot/entry.png")


def validate(data):
    if data[:8] != PNG_SIGNATURE:
        raise ValidationError("signature: not a PNG file")
    if len(data) > MAX_BYTES:
        raise ValidationError(f"size: {len(data)} bytes exceeds {MAX_BYTES} bytes")
    offset = 8
    index = 0
    width = height = None
    seen_iend = False
    while offset < len(data):
        if len(data) - offset < 12:
            raise ValidationError("chunk: truncated chunk header")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        ctype = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValidationError("chunk: truncated chunk data")
        payload = data[offset + 8:offset + 8 + length]
        stored_crc = struct.unpack(">I", data[offset + 8 + length:end])[0]
        actual_crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
        if actual_crc != stored_crc:
            raise ValidationError(f"crc: chunk {ctype!r} CRC mismatch")
        if index == 0 and ctype != b"IHDR":
            raise ValidationError("ihdr: first chunk is not IHDR")
        if ctype == b"IHDR":
            if length != 13:
                raise ValidationError("ihdr: bad length")
            width, height = struct.unpack(">II", payload[:8])
        index += 1
        offset = end
        if ctype == b"IEND":
            if length != 0:
                raise ValidationError("iend: bad length")
            seen_iend = True
            break
    if width is None or height is None:
        raise ValidationError("ihdr: missing")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValidationError(
            f"dimensions: {width}x{height} exceeds {MAX_DIMENSION}x{MAX_DIMENSION}"
        )
    if not seen_iend:
        raise ValidationError("iend: missing")
    if offset != len(data):
        raise ValidationError("trailing: data after IEND")
    return width, height


def output_dir():
    configured = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    return os.path.realpath(os.path.abspath(configured))


def main():
    path = png_path()
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        print(f"read: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    try:
        validate(data)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    out_dir = output_dir()
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        print(f"output-dir: cannot create {out_dir}: {exc}", file=sys.stderr)
        return 1
    out_path = os.path.join(out_dir, "entry.png")
    try:
        with open(out_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        print(f"write: cannot write {out_path}: {exc}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(data).hexdigest()
    print(f"{out_path} {len(data)} bytes sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
