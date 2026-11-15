from common_utils import common_loaders


def _load_map(stream, with_value):
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    entries = []
    positions = {}
    map_items = stream.loadNumericType(4)
    for i in range(map_items):
        entry = {}
        key = stream.loadAsciiString()
        entry['map_key'] = key[0]
        entry['items'] = []
        collection_items = stream.loadNumericType(4)
        for j in range(collection_items):
            # The first string is the object id of the target
            item = {}
            item['object_id'] = stream.loadAsciiString()[0]
            # kernel: the second string names the reference built from the item
            item['name'] = stream.loadAsciiString()[0]
            if with_value:
                item['value'] = common_loaders.loadMCDValueFromObjectStream(stream)
            entry['items'].append(item)
        common_loaders.put_map_entry(entries, positions, common_loaders.kernel_string_key(key), entry)
    return entries


def load(stream):
    obj = {}
    
    # No setters; the comment on each mapping names what the kernel looks it up with
    obj['unknown_1'] = _load_map(stream, False) # looked up with the name of the base variant
    obj['unknown_2'] = _load_map(stream, False) # looked up with the name of the base variant under an extra condition
    obj['unknown_3'] = _load_map(stream, False) # looked up with the name of the variant
    obj['unknown_4'] = _load_map(stream, True) # looked up with the name of the configuration data
    
    return obj
