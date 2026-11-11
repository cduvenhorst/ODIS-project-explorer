import re


# The content is upper-case hex text in all known data; the conversion to bytes does not
# decrypt or decompress anything
_HEX_TEXT = re.compile(rb'(?:[0-9A-Fa-f]{2})*')


def load(stream):
    # Single part form: the content is an embedded string behind the type code
    text = stream.loadNativeAsciiString()
    return {'is_big_data': False, 'inline_flash_data_length': len(text or '')}


def load_big_data(stream, content_parts: list[bytearray]) -> dict:
    """Describe a big data record from its content parts; reads nothing from the stream."""
    return {'is_big_data': True, 'inline_flash_data_length': sum(len(part) for part in content_parts)}


def content_bytes(parts: list[bytearray]) -> bytes:
    """Return the flash content of a record's parts as bytes.

    One part holds the content as an embedded string behind the type code, several parts hold
    it from the second part on. Raises ValueError if the text is not hex of even length.
    """
    if len(parts) == 1:
        # Type code, length word, text; anything after the text (the end marker) is ignored
        first = parts[0]
        length_word = int.from_bytes(first[2:6], 'little')
        text = bytes(first[6:6 + (length_word & 0x7FFFFFFF)]) if length_word & 0x80000000 else b''
    else:
        text = b''.join(parts[1:])
    if not _HEX_TEXT.fullmatch(text):
        raise ValueError('Inline flash data is not hex text of even length')
    return bytes.fromhex(text.decode('ascii'))
