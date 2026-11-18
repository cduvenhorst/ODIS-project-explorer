"""Hexdump in the format of ``hexdump -C``."""

from typing import Iterator

_LINE_WIDTH = 16


def _format_line(offset: int, chunk: bytes) -> str:
    hex_part = ''
    for index in range(_LINE_WIDTH):
        if index == 8:
            hex_part += ' '
        hex_part += '%02x ' % chunk[index] if index < len(chunk) else '   '
    text = ''.join(chr(byte) if 0x20 <= byte <= 0x7e else '.' for byte in chunk)
    return '%08x  %s |%s|\n' % (offset, hex_part, text)


def hexdump_lines(data: bytes) -> Iterator[str]:
    """Yield the lines of the dump, each ending with a newline.

    A full line equal to the previous full line is replaced by a single '*'
    line, and further equal lines add nothing. The final line is the total
    size as an offset; empty input yields nothing.
    """
    if not data:
        return
    previous = None
    collapsed = False
    for offset in range(0, len(data), _LINE_WIDTH):
        chunk = data[offset:offset + _LINE_WIDTH]
        if len(chunk) == _LINE_WIDTH and chunk == previous:
            if not collapsed:
                collapsed = True
                yield '*\n'
            continue
        collapsed = False
        previous = chunk if len(chunk) == _LINE_WIDTH else None
        yield _format_line(offset, chunk)
    yield '%08x\n' % len(data)


def hexdump_size(data: bytes) -> int:
    """Return the number of characters of the dump without building it."""
    return sum(len(line) for line in hexdump_lines(data))


def write_hexdump(data: bytes, path: str) -> None:
    """Write the dump to ``path`` as ASCII text with newline line endings."""
    with open(path, 'w', encoding='ascii', newline='') as handle:
        for line in hexdump_lines(data):
            handle.write(line)
