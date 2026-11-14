def load(stream):
    obj = {}
    
    # kernel: the five audience flags are booleans
    obj['supplier'] = bool(stream.loadOneByteType())
    obj['development'] = bool(stream.loadOneByteType())
    obj['manufacturing'] = bool(stream.loadOneByteType())
    obj['after_sales'] = bool(stream.loadOneByteType())
    obj['after_market'] = bool(stream.loadOneByteType())
    
    return obj
