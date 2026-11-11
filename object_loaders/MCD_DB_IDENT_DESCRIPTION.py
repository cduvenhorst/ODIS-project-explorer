def load(stream):
    obj = {}
    
    obj['data_primitive_name'] = stream.loadAsciiString()[0]
    
    # No setter; name proposed for the flag (weakly supported)
    obj['is_response_parameter_name'] = bool(stream.loadOneByteType())
    
    # One string follows in either case
    obj['response_parameter_name'] = None
    obj['response_parameter_short_name_path'] = None
    if obj['is_response_parameter_name']:
        obj['response_parameter_name'] = stream.loadAsciiString()[0]
    else:
        obj['response_parameter_short_name_path'] = stream.loadAsciiString()[0]
    
    return obj
