from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['diag_com_primitive_ref'] = common_loaders.load_DbDiagComObjectReference(stream)
    
    # kernel: both response parameter names are present, the one not read is None, and the
    # path flag (dbResponseParameterIsShortNamePath) is always present
    obj['response_parameter_name'] = None
    obj['response_parameter_short_name_path'] = None
    obj['response_parameter_is_short_name_path'] = bool(stream.loadOneByteType())
    if obj['response_parameter_is_short_name_path']:
        obj['response_parameter_short_name_path'] = stream.loadAsciiString()[0]
    else:
        obj['response_parameter_name'] = stream.loadAsciiString()[0]
    
    obj['expected_value_string'] = stream.loadUnicodeString()[0]
    
    return obj
