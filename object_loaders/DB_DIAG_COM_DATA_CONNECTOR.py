from classes import DbObject
from common_utils import common_loaders


def load(stream):
    obj = {}
    
    # Each parameter is addressed either by short name or by short name path; only the one that was read is set
    obj['write_param_is_short_name_path'] = bool(stream.loadOneByteType())
    write_param = stream.loadAsciiString()[0]
    obj['write_param_short_name'] = None if obj['write_param_is_short_name_path'] else write_param
    obj['write_param_short_name_path'] = write_param if obj['write_param_is_short_name_path'] else None
    
    obj['read_param_is_short_name_path'] = bool(stream.loadOneByteType())
    read_param = stream.loadAsciiString()[0]
    obj['read_param_short_name'] = None if obj['read_param_is_short_name_path'] else read_param
    obj['read_param_short_name_path'] = read_param if obj['read_param_is_short_name_path'] else None
    
    # The outer byte comes first; the object (with its own presence byte) only follows when it is non-zero
    obj['read_diag_com_primitive'] = None
    if stream.loadOneByteType():
        obj['read_diag_com_primitive'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    
    obj['write_diag_com_primitive'] = None
    if stream.loadOneByteType():
        obj['write_diag_com_primitive'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    
    obj['uncompressed_size'] = stream.loadNumericType(4)
    obj['start_address'] = stream.loadNumericType(4)
    
    obj['write_param_value_map'] = common_loaders.loadAsciiToUnicodeStringMap(stream)
    obj['write_param_value_sn_path_map'] = common_loaders.loadAsciiToUnicodeStringMap(stream)
    obj['read_param_value_map'] = common_loaders.loadAsciiToUnicodeStringMap(stream)
    obj['read_param_value_sn_path_map'] = common_loaders.loadAsciiToUnicodeStringMap(stream)
    
    return obj
