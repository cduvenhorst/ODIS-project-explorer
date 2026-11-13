from common_utils import enum_converters


def load(stream):
    obj = {}
    
    EDbPhysicalDataType_enum = stream.loadEnumSmallRange()
    # kernel: the physical base type has its own enumeration; an unknown value is kept as its number
    obj['base_data_type'] = enum_converters.enum_name_or_number(enum_converters.get_EDbPhysicalDataType, EDbPhysicalDataType_enum)
    # derived, not stored by the kernel
    try:
        obj['base_data_type_as_mcd_data_type'] = enum_converters.get_MCDDataType(enum_converters.map_enum_EDbPhysicalDataType_to_MCDDataType(EDbPhysicalDataType_enum))
    except RuntimeError:
        obj['base_data_type_as_mcd_data_type'] = None
    
    obj['is_precision_available'] = bool(stream.loadNumericType(1))
    if obj['is_precision_available']:
        obj['precision'] = stream.loadNumericType(2)
    
    obj['display_radix'] = stream.loadEnumSmallRange()
    
    return obj
