from classes import DbObject


def load(stream):
    obj = []
    
    # loadCollectionFromObjectStream
    
    collection_items = stream.loadNumericType(2)
    for i in range(collection_items):
        obj.append(DbObject.load_object_from_stream_if_exists(stream)) # MCDDbItemValueImpl
    
    return obj
