from classes import DbObject


def load(stream):
    obj = []
    
    # loadCollectionFromObjectStream
    
    collection_items = stream.loadNumericType(2)
    for i in range(collection_items):
        # kernel: fails when an element is empty; kept readable for VW projects
        obj.append(DbObject.load_object_from_stream_if_exists(stream)) # MCDDbSystemItemImpl
    
    return obj
