from common_utils import common_loaders


def _load_map(stream, with_value):
    # Keys can repeat, so the entries stay a list in read order
    entries = []
    for _ in range(stream.loadNumericType(4)):
        entry = {}
        entry['map_key'] = stream.loadAsciiString()[0]
        entry['items'] = []
        for _ in range(stream.loadNumericType(4)):
            # The first string is the object id of the target
            item = {}
            item['object_id'] = stream.loadAsciiString()[0]
            item['unknown_1'] = stream.loadAsciiString()[0]
            if with_value:
                item['value'] = common_loaders.loadMCDValueFromObjectStream(stream)
            entry['items'].append(item)
        entries.append(entry)
    return entries


def load(stream):
    obj = {}
    
    # No setters; the comment on each mapping names what the kernel looks it up with
    obj['unknown_1'] = _load_map(stream, False) # looked up with the name of the base variant
    obj['unknown_2'] = _load_map(stream, False) # looked up with the name of the base variant under an extra condition
    obj['unknown_3'] = _load_map(stream, False) # looked up with the name of the variant
    obj['unknown_4'] = _load_map(stream, True) # looked up with the name of the configuration data
    
    return obj
