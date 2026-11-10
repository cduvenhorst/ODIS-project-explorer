def load(stream):
    obj = {}
    
    obj['description_id'] = stream.loadNativeAsciiString()
    obj['long_name_id'] = stream.loadNativeAsciiString()
    obj['unique_object_id'] = stream.loadNativeAsciiString()
    obj['description'] = stream.loadNativeUnicodeString()
    obj['long_name'] = stream.loadNativeUnicodeString()
    obj['short_name'] = stream.loadNativeAsciiString()
    
    return obj
