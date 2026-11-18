"""Hints about the kind of a flash data block: header, method byte, entropy.

The reading of the method byte (upper nibble: compression, lower nibble:
encryption) follows ISO 14229. It is a reading of that standard and is not
confirmed by the kernel or by any job.
"""
import math
from collections import Counter

ENTROPY_THRESHOLD = 7.5

_GZIP_MAGIC = b'\x1f\x8b'
_XZ_MAGIC = b'\xfd7zXZ\x00'


def entropy(data: bytes) -> float:
    """Shannon entropy in bits per byte."""
    if not data:
        return 0.0
    total = len(data)
    return abs(-sum(n / total * math.log2(n / total) for n in Counter(data).values()))


def _method_text(method: int) -> str:
    compressed = method & 0xF0 != 0
    encrypted = method & 0x0F != 0
    if compressed and encrypted:
        return 'compressed and encrypted'
    if compressed:
        return 'compressed'
    if encrypted:
        return 'encrypted'
    return 'not compressed, not encrypted'


def describe_data_kind(data: bytes, method: int | None = None, method_source: str = '') -> str:
    if not data:
        return 'empty'
    parts = []
    if data.startswith(_GZIP_MAGIC):
        parts.append('gzip (header)')
    elif data.startswith(_XZ_MAGIC):
        parts.append('xz (header)')
    if method is not None:
        parts.append('%s (%s 0x%02X, ISO 14229 reading)' % (_method_text(method), method_source, method))
    value = entropy(data)
    if value >= ENTROPY_THRESHOLD:
        parts.append('compressed or encrypted (entropy %.2f)' % value)
    else:
        parts.append('not compressed or encrypted as a whole (entropy %.2f)' % value)
    return '; '.join(parts)
