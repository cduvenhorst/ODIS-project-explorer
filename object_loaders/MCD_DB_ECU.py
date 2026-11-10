from classes import DbObject


def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    
    obj['unique_object_id'] = stream.loadAsciiString()[0] # UniqueObjectIdentifier; not always empty
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    
    obj['location_refs'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        item['name'] = stream.loadAsciiString()[0]
        
        item['reference'] = {}
        item['reference']['object_id'] = stream.loadAsciiString()[0]
        item['reference']['pool_id'] = stream.loadAsciiString()[0]
        item['reference']['access_key'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAccessKeyImpl
        
        obj['location_refs'].append(item)
    
    return obj
