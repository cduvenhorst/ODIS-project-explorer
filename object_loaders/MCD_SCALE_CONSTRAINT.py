from common_utils import enum_converters
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['interval'] = DbObject.load_object_from_stream_if_exists(stream) # MCDIntervalImpl
    
    # kernel: an unknown range info is kept as its number
    obj['range_info'] = enum_converters.enum_name_or_number(enum_converters.get_MCDRangeInfo, 0x600 + stream.loadNumericType(1))
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['short_label'] = stream.loadAsciiString()[0]
    obj['short_label_id'] = stream.loadAsciiString()[0]
    
    obj['is_computed'] = bool(stream.loadOneByteType())
    
    return obj
