from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['bit_position'] = stream.loadOneByteType()
    obj['byte_position'] = stream.loadNumericType(4)
    obj['is_byte_position_available'] = True
    
    obj['dop_base_reference'] = common_loaders.load_reference(stream, False, False) # DbObjectReference : DbDopBase
    
    return obj
