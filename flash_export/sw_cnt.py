"""Reader for SW-CNT flash containers.

The containers are read by the vendor's flashing job (a Java job), not by the
diagnostic kernel. The format follows the observed data; the encoding is
ISO-8859-1.
"""
import base64
import binascii
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

_HEADER_LINE = re.compile(r'^[A-Za-z][A-Za-z0-9 -]*:')


@dataclass(frozen=True)
class SwCntBlock:
    index: int                      # 1-based order in the document
    name: str                       # DATENBLOCK-NAME, stripped; '' when missing
    data_format: int | None         # DATENBLOCK-FORMAT
    start_address: int | None       # START-ADR
    uncompressed_size: int | None   # GROESSE-DEKOMPRIMIERT
    data: bytes | None              # decoded DATENBLOCK-DATEN; None when it cannot be decoded


def decode_mime_base64(text):
    """Decode Base64 text that may carry leading MIME header lines.

    Lenient: header lines and their continuations are skipped, all white space
    is dropped and missing '=' padding is added. Returns None when the text is
    not valid Base64.
    """
    lines = text.splitlines()
    position = 0
    in_header = False
    while position < len(lines):
        line = lines[position]
        if not line.strip():
            in_header = False
        elif _HEADER_LINE.match(line):
            in_header = True
        elif in_header and line[0] in ' \t':
            pass
        else:
            break
        position += 1
    payload = ''.join(''.join(lines[position:]).split())
    payload += '=' * (-len(payload) % 4)
    try:
        return base64.b64decode(payload, validate=True)
    except binascii.Error:
        return None


def _number(parent, tag):
    element = parent.find(tag)
    if element is None or element.text is None:
        return None
    try:
        return int(element.text.strip(), 16)
    except ValueError:
        return None


def _parse(raw):
    """Parse a document; an XML declaration decides the encoding, else ISO-8859-1."""
    if raw.startswith(b'<?xml'):
        return ET.fromstring(raw)
    return ET.fromstring(raw.decode('iso-8859-1'))


def read_sw_cnt(raw):
    """Read the data blocks of a SW-CNT container.

    Returns None when the root element is not SW-CNT; raises ET.ParseError
    when the text is not well-formed XML.
    """
    root = _parse(raw)
    if root.tag != 'SW-CNT':
        return None
    blocks = []
    for index, element in enumerate(root.findall('DATEN/DATENBLOECKE/DATENBLOCK'), start=1):
        name = element.findtext('DATENBLOCK-NAME') or ''
        data_element = element.find('DATENBLOCK-DATEN')
        data = None
        if data_element is not None:
            data = decode_mime_base64(data_element.text or '')
        blocks.append(SwCntBlock(index, name.strip(), _number(element, 'DATENBLOCK-FORMAT'),
                                 _number(element, 'START-ADR'),
                                 _number(element, 'GROESSE-DEKOMPRIMIERT'), data))
    return blocks


def read_sw_cnt_areas(raw):
    """Read the data areas (DATENBEREICHE/DATENBEREICH) of a SW-CNT container.

    Returns None when the root element is not SW-CNT; raises ET.ParseError
    when the text is not well-formed XML. The data format is not available.
    """
    root = _parse(raw)
    if root.tag != 'SW-CNT':
        return None
    areas = []
    for index, element in enumerate(root.findall('DATENBEREICHE/DATENBEREICH'), start=1):
        name = element.findtext('DATEN-NAME') or ''
        data_element = element.find('DATEN')
        data = None
        if data_element is not None:
            data = decode_mime_base64(data_element.text or '')
        areas.append(SwCntBlock(index, name.strip(), None, _number(element, 'START-ADR'),
                                _number(element, 'GROESSE-DEKOMPRIMIERT'), data))
    return areas
