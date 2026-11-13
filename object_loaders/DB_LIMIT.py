from common_utils import common_loaders
from common_utils import enum_converters


def load(stream):
    obj = {}
    
    # kernel: the limit value is read with getLimit
    obj['limit'] = common_loaders.loadMCDValueFromObjectStream(stream)
    # kernel: an unknown limit type is kept as its number
    obj['limit_type'] = enum_converters.enum_name_or_number(enum_converters.get_MCDLimitType, stream.loadNumericType(1) + 0x6D00)
    
    return obj
