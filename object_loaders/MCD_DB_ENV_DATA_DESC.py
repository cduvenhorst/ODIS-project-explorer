from classes import DbObject


def load(stream):
    obj = {}
    
    obj['description'] = stream.loadUnicodeString()[0]  # Description
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    # kernel: getEnvDataParamMap; the key is a DTC value, the value the short name of its environment data parameter
    obj['env_data_param_map'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        item['map_key'] = stream.loadNumericType(4)
        item['value'] = stream.loadAsciiString()[0]
        obj['env_data_param_map'].append(item)
    
    # Not a mistake, 1b is checked twice
    if stream.loadOneByteType():
        obj['all_value_db_env_data_param'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
    
    # kernel: each entry is added with addDbEnvDataParam(parameter, vector); the vector holds the
    # DTC values the parameter applies to
    obj['env_data_info_map'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        item['env_data_param'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
        
        # loadVectorFromObjectStream
        
        item['dtc_values'] = []
        vector_items = stream.loadNumericType(4)
        for j in range(vector_items):
            item['dtc_values'].append(stream.loadNumericType(4))
        
        obj['env_data_info_map'].append(item)
    
    return obj
