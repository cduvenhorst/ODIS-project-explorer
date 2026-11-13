from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    
    # kernel: reads the three identifiers without a check
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    
    obj['structure_dop_ref'] = None if not stream.loadOneByteType() else common_loaders.load_reference(stream, False, False) # DbObjectReference : DbDopBase
    
    return obj
