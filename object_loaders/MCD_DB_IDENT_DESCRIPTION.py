def load(stream):
    obj = {}
    
    obj['data_primitive_name'] = stream.loadAsciiString()[0]
    
    # kernel: stored as 0/1 without accessor; 1 means the name was read
    obj['is_response_parameter_name'] = bool(stream.loadOneByteType())
    
    # One string follows in either case
    obj['response_parameter_name'] = None
    obj['response_parameter_short_name_path'] = None
    if obj['is_response_parameter_name']:
        obj['response_parameter_name'] = stream.loadAsciiString()[0]
    else:
        obj['response_parameter_short_name_path'] = stream.loadAsciiString()[0]
    
    return obj
