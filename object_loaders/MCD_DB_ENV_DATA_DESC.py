from classes import DbObject
from common_utils import common_loaders


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
    # kernel: std::map ordered by the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['env_data_parameter_map'] = []
    positions = {}
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        item['map_key'] = stream.loadNumericType(4)
        item['value'] = stream.loadAsciiString()[0]
        common_loaders.put_map_entry(obj['env_data_parameter_map'], positions, item['map_key'], item)
    
    # Not a mistake, 1b is checked twice
    # kernel: getAllValueEnvDataParam reports 'not set' without the flag
    obj['all_value_env_data_parameter'] = None
    if stream.loadOneByteType():
        obj['all_value_env_data_parameter'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
    
    # kernel: each entry is added with addDbEnvDataParam(parameter, vector); the vector holds the
    # DTC values the parameter applies to
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['env_data_information_map'] = []
    positions = {}
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        item['env_data_parameter'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
        
        # loadVectorFromObjectStream
        
        item['dtc_values'] = []
        vector_items = stream.loadNumericType(4)
        for j in range(vector_items):
            item['dtc_values'].append(stream.loadNumericType(4))
        
        common_loaders.put_map_entry(obj['env_data_information_map'], positions, common_loaders.kernel_string_key(key), item)
    
    return obj
