from classes import DbObject


def load(stream):
    obj = {}
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['env_data_param_map'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        item['key'] = stream.loadNumericType(4)
        item['string'] = stream.loadAsciiString()[0]
        obj['env_data_param_map'].append(item)
    
    # Not a mistake, 1b is checked twice
    if stream.loadOneByteType():
        obj['all_value_db_env_data_param'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
    
    obj['env_data_params'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        item['string'] = stream.loadAsciiString()[0]
        item['param'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
        
        # loadVectorFromObjectStream
        
        item['vector'] = []
        vector_items = stream.loadNumericType(4)
        for j in range(vector_items):
            item['vector'].append(stream.loadNumericType(4))
        
        obj['env_data_params'].append(item)
    
    return obj
