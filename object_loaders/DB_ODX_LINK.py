def load(stream):
    obj = {}
    
    obj['id_reference'] = stream.loadAsciiString()[0]
    obj['doc_ref'] = stream.loadAsciiString()[0]
    obj['is_layer_doc_type'] = bool(stream.loadOneByteType())
    
    return obj
