"""Reading of ODX flash documents (root ODX with a FLASH child).

Reading follows ASAM ODX packaging; it is not kernel-identical, because the kernel does not read PDX files at
run time. Documents can be very large, so they are parsed incrementally and finished FLASHDATA elements are
cleared. References (ID-REF) may point forward or backward and are resolved after parsing.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

_HEX = re.compile(r'(?:0[xX])?[0-9A-Fa-f]+')


@dataclass(frozen=True)
class OdxFlashBlock:
    index: int
    name: str
    block_type: str
    sessions: tuple[str, ...]
    part_numbers: tuple[str, ...]
    start_address: int | None
    uncompressed_size: int | None
    method: int | None
    flash_data: str | None
    data_file: str | None
    has_data: bool


@dataclass(frozen=True)
class OdxFlashDocument:
    ecus: tuple[str, ...]
    blocks: tuple[OdxFlashBlock, ...]


def _local(tag) -> str:
    return tag.rpartition('}')[2] if isinstance(tag, str) else ''


def _child(element, name):
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _text(element, name) -> str | None:
    child = _child(element, name)
    return None if child is None else (child.text or '').strip()


def _number(text, base):
    if text is None or (base == 16 and not _HEX.fullmatch(text)):
        return None
    try:
        return int(text, base)
    except ValueError:
        return None


def is_flash_document(stream) -> bool:
    """True when the root is ODX and its first child is FLASH; only the start of the stream is read."""
    depth = 0
    try:
        for event, element in ET.iterparse(stream, events=('start',)):
            depth += 1
            name = _local(element.tag)
            if depth == 1:
                if name != 'ODX':
                    return False
            else:
                return name == 'FLASH'
    except ET.ParseError:
        return False
    return False


def _flash_data_info(element) -> dict:
    data = _child(element, 'DATA')
    datafile = _child(element, 'DATAFILE')
    return {
        'name': _text(element, 'SHORT-NAME') or '',
        'method': _text(element, 'ENCRYPT-COMPRESS-METHOD'),
        'data_file': None if datafile is None else (datafile.text or '').strip(),
        'has_data': data is not None,
    }


def read_flash_document(stream) -> OdxFlashDocument:
    """Read the block metadata of a flash document; FLASHDATA contents are not kept."""
    ecus: list[str] = []
    blocks: list[dict] = []
    sessions: list[tuple[str, list[str]]] = []
    descs: list[tuple[str, str]] = []
    flash: dict[str, dict] = {}
    for _event, element in ET.iterparse(stream, events=('end',)):
        name = _local(element.tag)
        if name == 'FLASHDATA':
            flash[element.get('ID') or ''] = _flash_data_info(element)
            element.clear()
        elif name == 'DATABLOCK':
            segments = [s for s in element.iter() if _local(s.tag) == 'SEGMENT']
            starts = [_number(_text(s, 'SOURCE-START-ADDRESS'), 16) for s in segments
                      if _child(s, 'SOURCE-START-ADDRESS') is not None]
            sizes = [_number(_text(s, 'UNCOMPRESSED-SIZE'), 10) for s in segments
                     if _child(s, 'UNCOMPRESSED-SIZE') is not None]
            ref = _child(element, 'FLASHDATA-REF')
            blocks.append({
                'id': element.get('ID') or '',
                'name': _text(element, 'SHORT-NAME') or '',
                'type': element.get('TYPE') or '',
                'start': min(starts) if starts and None not in starts else None,
                'size': sum(sizes) if sizes and None not in sizes else None,
                'ref': None if ref is None else ref.get('ID-REF'),
            })
            element.clear()
        elif name == 'SESSION':
            refs = [r.get('ID-REF') or '' for r in element.iter() if _local(r.tag) == 'DATABLOCK-REF']
            sessions.append((_text(element, 'SHORT-NAME') or '', refs))
        elif name == 'SESSION-DESC':
            snref = _child(element, 'SESSION-SNREF')
            part = _text(element, 'PARTNUMBER')
            if snref is not None and part:
                descs.append((snref.get('SHORT-NAME') or '', part))
        elif name == 'LAYER-REF':
            if element.get('DOCREF'):
                ecus.append(element.get('DOCREF'))
    result = []
    for index, info in enumerate(blocks, start=1):
        block_sessions = tuple(dict.fromkeys(n for n, refs in sessions if info['id'] in refs))
        parts = tuple(dict.fromkeys(p for n, p in descs if n in block_sessions))
        data = flash.get(info['ref']) if info['ref'] is not None else None
        method_text = data['method'] if data else None
        method = _number(method_text, 16) if method_text is not None and len(method_text) <= 2 else None
        result.append(OdxFlashBlock(
            index=index, name=info['name'], block_type=info['type'], sessions=block_sessions,
            part_numbers=parts, start_address=info['start'], uncompressed_size=info['size'], method=method,
            flash_data=data['name'] if data else None,
            data_file=data['data_file'] if data else None,
            has_data=bool(data and data['has_data'])))
    return OdxFlashDocument(ecus=tuple(ecus), blocks=tuple(result))


def read_intern_data(stream) -> dict[str, bytes]:
    """Map FLASHDATA short names to their decoded DATA; raises ValueError for malformed hex text."""
    contents: dict[str, bytes] = {}
    for _event, element in ET.iterparse(stream, events=('end',)):
        if _local(element.tag) != 'FLASHDATA':
            continue
        data = _child(element, 'DATA')
        if data is not None:
            name = _text(element, 'SHORT-NAME') or ''
            contents[name] = bytes.fromhex(''.join((data.text or '').split()))
        element.clear()
    return contents
