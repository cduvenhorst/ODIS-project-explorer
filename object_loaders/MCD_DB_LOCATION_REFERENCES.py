from classes import DbObject


def load(stream):
    obj = {}
    
    obj['object_id'] = stream.loadAsciiString()[0]
    obj['pool_id'] = stream.loadAsciiString()[0]
    
    # kernel: one optional access key
    obj['access_key'] = DbObject.load_object_from_stream_if_exists(stream)
    
    return obj
