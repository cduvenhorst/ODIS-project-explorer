from common_utils import common_loaders
from common_utils import enum_converters


def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    
    # UniqueObjectIdentifier, LongNameID and DescriptionID; not always empty
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    
    # kernel: an unknown category is kept as its number
    obj['category'] = enum_converters.enum_name_or_number(enum_converters.get_MCDUnitGroupCategory, stream.loadEnumMediumRange())
    
    # kernel: the references are read with getUnits
    obj['unit_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    return obj
