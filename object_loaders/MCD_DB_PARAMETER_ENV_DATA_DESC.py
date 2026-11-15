from classes import DbObject


def load(stream):
    obj = {}
    
    obj['is_parameter_short_name_path_available'] = bool(stream.loadOneByteType())
    # kernel: getParameterShortNamePath and getParameterName report 'not set' for the one not read
    obj['parameter_short_name_path'] = None
    obj['parameter_name'] = None
    if obj['is_parameter_short_name_path_available']:
        obj['parameter_short_name_path'] = stream.loadAsciiString()[0]
    else:
        obj['parameter_name'] = stream.loadAsciiString()[0]
    
    obj['env_data_desc'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbEnvDataDescImpl
    
    # kernel: a missing environment data description aborts loading
    if obj['env_data_desc'] is None:
        raise RuntimeError('db environment data not set')
    
    obj['byte_length'] = stream.loadNumericType(2)
    
    return obj
