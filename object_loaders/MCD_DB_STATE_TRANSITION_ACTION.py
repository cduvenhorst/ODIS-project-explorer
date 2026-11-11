from common_utils import common_loaders


# Value, request parameter switch and request parameter name, shared with MCD_DB_PRECONDITION_DEFINITION
def load_value_and_request_parameter(stream):
    obj = {}
    
    obj['value'] = stream.loadUnicodeString()[0] # getValue; the string is converted to an MCD value at run time
    obj['request_parameter_is_short_name_path'] = bool(stream.loadOneByteType())
    
    # One string, stored in one of two slots depending on the switch; the other key stays None
    name = stream.loadAsciiString()[0]
    obj['request_parameter_short_name'] = None
    obj['request_parameter_short_name_path'] = None
    if obj['request_parameter_is_short_name_path']:
        obj['request_parameter_short_name_path'] = name
    else:
        obj['request_parameter_short_name'] = name
    
    return obj


def load(stream):
    obj = {}
    
    obj['diag_com_primitive'] = common_loaders.load_DbDiagComObjectReference(stream)
    obj.update(load_value_and_request_parameter(stream))
    
    return obj
