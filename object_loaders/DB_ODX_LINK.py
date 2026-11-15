def load(stream):
    obj = {}
    
    obj['id_reference'] = stream.loadAsciiString()[0]
    obj['document_reference'] = stream.loadAsciiString()[0]
    obj['is_layer_document_type'] = bool(stream.loadOneByteType())
    
    return obj
