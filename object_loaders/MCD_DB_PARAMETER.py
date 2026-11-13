from common_utils import common_loaders
from common_utils import enum_converters
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0] # DescriptionID; not always empty
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['bit_position'] = stream.loadNumericType(1)
    obj['byte_position'] = stream.loadNumericType(4)
    
    flags = stream.loadNumericType(1)
    
    obj['default_mcd_value'] = None
    if flags & (1 << 0):
        obj['default_mcd_value'] = common_loaders.loadMCDValueFromObjectStream(stream)
    
    obj['display_level'] = stream.loadNumericType(4)
    
    obj['semantic'] = None
    if flags & (1 << 1):
        obj['semantic'] = stream.loadAsciiString()[0]
    
    obj['sys_param'] = stream.loadAsciiString()[0]
    
    # kernel: keeps an unknown parameter type and reads on
    obj['mcd_parameter_type'] = enum_converters.enum_name_or_number(enum_converters.get_MCDParameterType, 0x7000 + stream.loadNumericType(1))
    
    # kernel: cached MCDDataType of the parameter, 0xFF means not set
    obj['parameter_type'] = None
    parameter_type = stream.loadEnumSmallRange()
    if parameter_type != 0xFF:
        obj['parameter_type'] = enum_converters.enum_name_or_number(enum_converters.get_MCDDataType, parameter_type)
    
    obj['diag_coded_type'] = None
    if flags & (1 << 2):
        obj['diag_coded_type'] = DbObject.load_object_from_stream_if_exists(stream) # DbDiagCodedType
    
    # kernel: DbObjectReference<DbDopBase>
    obj['dop_base_ref'] = None
    if flags & (1 << 3):
        obj['dop_base_ref'] = common_loaders.load_reference(stream, False)
    
    obj['dop_base'] = None
    if flags & (1 << 4):
        obj['dop_base'] = DbObject.load_object_from_stream_if_exists(stream) # DopBase
    
    obj['is_byte_pos_available'] = bool(flags & (1 << 5))
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_refs'] = []
    if flags & (1 << 6):
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['is_protocol_parameter'] = bool(flags & (1 << 7))
    
    obj['nrc_const_values'] = None
    if obj['mcd_parameter_type'] == 'eNRC_CONST':
        obj['nrc_const_values'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_VALUES
    
    return obj
