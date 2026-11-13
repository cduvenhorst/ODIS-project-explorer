from object_loaders import MCD_DB_PARAMETER
from classes import DbObject


def load(stream):
    obj = MCD_DB_PARAMETER.load(stream) # super = MCDDbParameterImpl
    
    obj['protocol_parameter_class'] = stream.loadEnumMediumRange()
    obj['protocol_parameter_type'] = stream.loadEnumMediumRange()
    
    obj['parameters'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParametersImpl
    
    # kernel: a protocol parameter with sub-parameters is a structure; only the presence of the collection counts
    if obj['parameters'] is not None:
        obj['parameter_type'] = 'eSTRUCTURE'
    
    obj['protocol_stack_short_name'] = stream.loadAsciiString()[0]
    obj['protocol_short_name'] = stream.loadAsciiString()[0]
    
    obj['protocol_parameter_usage'] = stream.loadEnumMediumRange()
    
    return obj
