from common_utils import common_loaders

INLINE_PREFIX = 'DSA_INLINE_'
OBJECT_MARKER = 'DDDSSSAAA'
BIG_DATA_MARKER = 'DDDSSSBBB'
MARKER_SEARCH_LIMIT = 1000


def decode_data_reference(name: str | None) -> dict:
    """Describe where the flash data named by `name` is stored.

    Returns a dict whose 'kind' is 'external_file', 'object', 'big_data_object' or
    'inline_content'. Reads nothing and does not raise.
    """
    if name is None or len(name) <= len(INLINE_PREFIX) or not name.startswith(INLINE_PREFIX):
        return {'kind': 'external_file', 'file_name': name}
    window = name[:MARKER_SEARCH_LIMIT]
    for marker, kind in ((OBJECT_MARKER, 'object'), (BIG_DATA_MARKER, 'big_data_object')):
        position = window.find(marker, len(INLINE_PREFIX))
        if position >= 0:
            return {'kind': kind, 'pool_id': name[len(INLINE_PREFIX):position],
                    'object_id': name[position + len(marker):]}
    return {'kind': 'inline_content', 'content_length': len(name) - len(INLINE_PREFIX)}


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    obj['data_file_name_or_inline_flash_data'] = stream.loadAsciiString()[0]
    obj['data_reference'] = decode_data_reference(obj['data_file_name_or_inline_flash_data'])
    obj['late_bound_or_is_inline'] = bool(stream.loadOneByteType())
    # 0x6B01/0x6B02/0x6B03 are inferred as binary/Intel hex/Motorola, no name table was found
    obj['data_format'] = stream.loadNumericType(2)
    obj['encryption_compression_method'] = common_loaders.loadMCDValueFromObjectStream(stream)
    obj['flash_file_sub_dir_name'] = stream.loadAsciiString()[0]
    
    return obj
