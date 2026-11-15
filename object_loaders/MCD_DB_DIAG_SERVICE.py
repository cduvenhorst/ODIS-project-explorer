from common_utils import common_loaders
from common_utils import enum_converters
from object_loaders import MCD_DB_DATA_PRIMITIVE


def load(stream):
    obj = {}
    
    obj['service_protocol_parameters'] = common_loaders.loadServiceProtocolParametersMap(stream)
    
    # kernel: an unknown runtime mode is kept as its number
    obj['runtime_mode'] = enum_converters.enum_name_or_number(enum_converters.get_MCDRuntimeMode, stream.loadEnumMediumRange())
    
    obj['is_multiple'] = bool(stream.loadOneByteType())
    
    obj['data_primitive'] = {'#OBJECT_TYPE': 'MCD_DB_DATA_PRIMITIVE'}
    obj['data_primitive'].update(MCD_DB_DATA_PRIMITIVE.load(stream))
    
    return obj
