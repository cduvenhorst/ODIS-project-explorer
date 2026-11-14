from common_utils import enum_converters
from object_loaders import MCD_DB_DIAG_SERVICE


def load(stream):
    obj = {}
    
    # kernel: an unknown addressing mode is kept as its number by the setter setAddressingMode
    obj['addressing_mode'] = enum_converters.enum_name_or_number(enum_converters.get_MCDAddressingMode, 0x6000 + stream.loadNumericType(1))
    
    obj.update(MCD_DB_DIAG_SERVICE.load(stream)) # super = MCDDbDiagServiceImpl
    
    return obj
