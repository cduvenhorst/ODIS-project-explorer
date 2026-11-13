from common_utils import common_loaders
from common_utils import enum_converters
from classes import DbObject


# kernel: initEncoding replaces an encoding that does not fit the base data type
def initEncoding(base_data_type, encoding):
    match base_data_type:
        case 'eDB_INT32':
            if encoding not in ['e1C', 'e2C', 'eSM']:
                encoding = 'e2C'
        case 'eDB_UINT32':
            if encoding not in ['eBCD_P', 'eBCD_UP']:
                encoding = 'eNONE'
        case 'eDB_FLOAT32' | 'eDB_FLOAT64':
            if encoding != 'eIEEE754':
                encoding = 'eNONE'
        case 'eDB_ASCIISTRING':
            if encoding not in ['eISO_8859_1', 'eISO_8859_2', 'eWINDOWS_1252']:
                encoding = 'eISO_8859_1'
        case 'eDB_UTF8STRING':
            encoding = 'eUTF_8'
        case 'eDB_UNICODE2STRING':
            encoding = 'eUCS_2'
        case 'eDB_BYTEFIELD':
            if encoding not in ['eBCD_P', 'eBCD_UP']:
                encoding = 'eNONE'
        case 'eDB_BITFIELD':
            encoding = 'eNONE'
        case _:
            encoding = 'eNONE'
    
    return encoding


def load(stream):
    obj = {}
    
    # kernel: the type is read with getCodedType; an unknown type is kept as its number
    obj['coded_type'] = enum_converters.enum_name_or_number(enum_converters.get_EDbDiagCodedType, stream.loadEnumSmallRange())
    
    if obj['coded_type'] == 'eMIN_MAX_LENGTH_TYPE':
        obj['max_length'] = stream.loadNumericType(4)
        obj['min_length'] = stream.loadNumericType(4)
        obj['termination'] = enum_converters.enum_name_or_number(enum_converters.get_EDbTermination, stream.loadEnumSmallRange())
    else:
        obj['bit_length'] = stream.loadNumericType(4)
        
    if obj['coded_type'] == 'eSTANDARD_LENGTH_TYPE':
        obj['bit_mask'] = common_loaders.loadBytefieldFromObjectStream(stream)
    
    EDbDataType_enum = stream.loadEnumSmallRange()
    # kernel: an unknown base data type is kept as its number
    obj['base_data_type'] = enum_converters.enum_name_or_number(enum_converters.get_EDbDataType, EDbDataType_enum)
    # derived, not stored by the kernel
    try:
        obj['base_data_type_as_mcd_data_type'] = enum_converters.get_MCDDataType(enum_converters.map_enum_EDbDataType_to_MCDDataType(EDbDataType_enum))
    except RuntimeError:
        obj['base_data_type_as_mcd_data_type'] = None
    encoding = enum_converters.enum_name_or_number(enum_converters.get_EDbEncoding, stream.loadEnumSmallRange())
    obj['encoding'] = initEncoding(obj['base_data_type'], encoding)
    
    obj['is_high_low_byte_order'] = bool(stream.loadOneByteType())
    # kernel: the flag is read with isCondensedBitMask
    obj['is_condensed_bit_mask'] = bool(stream.loadOneByteType())
    
    if obj['coded_type'] == 'ePARAM_LENGTH_INFO_TYPE':
        # kernel: fails when the length key parameter is missing; kept readable for VW projects
        obj['length_key_parameter'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbParameterImpl
    
    return obj
