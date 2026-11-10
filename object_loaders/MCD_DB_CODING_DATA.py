def load(stream):
    obj = {}
    
    # Unlike most other objects, the names are stored in the standard order
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    
    obj['file_name'] = stream.loadAsciiString()[0]
    obj['is_late_bound'] = bool(stream.loadOneByteType())
    
    return obj
