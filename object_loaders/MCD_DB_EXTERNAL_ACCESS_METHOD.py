def load(stream):
    obj = {}
    
    obj['unique_object_id'] = stream.loadAsciiString()[0] # no setter; named after the slot of the base class
    obj['method'] = stream.loadUnicodeString()[0] # getMethod
    
    return obj
