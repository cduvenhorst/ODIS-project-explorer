from common_utils import enum_converters


def load(stream):
    obj = {}
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    obj['pin_number'] = stream.loadNumericType(2)
    obj['pin_type'] = enum_converters.get_MCDConnectorPinType(stream.loadEnumMediumRange())
    
    return obj
