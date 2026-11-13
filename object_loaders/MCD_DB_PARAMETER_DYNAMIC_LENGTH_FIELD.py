from common_utils import common_loaders
from object_loaders import DB_DOP_FIELD


def load(stream):
    obj = DB_DOP_FIELD.load(stream) # super = DbDopField
    
    # kernel: getOffset
    obj['offset'] = stream.loadNumericType(4)
    
    # kernel: DbObjectReference<DbDopBase>, the DOP that determines the number of items
    obj['dop_base_ref'] = common_loaders.load_reference(stream, False, False) # DbObjectReference : DbDopBase
    
    # kernel: getSimpleBytePosition
    obj['simple_byte_position'] = stream.loadNumericType(4)
    
    # kernel: setSimpleBitPosition
    obj['simple_bit_position'] = stream.loadOneByteType()
    
    return obj
