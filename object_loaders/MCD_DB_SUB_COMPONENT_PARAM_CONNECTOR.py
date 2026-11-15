from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['diag_com_primitive_name'] = stream.loadAsciiString()[0]
    
    for key in ('sub_component_in_parameter_names', 'sub_component_out_parameter_names'):
        # kernel: std::map ordered by the string number of the name; a later duplicate name replaces the earlier entry; kept in read order
        obj[key] = []
        positions = {}
        param_count = stream.loadNumericType(2)
        for i in range(param_count):
            param = {}
            name = stream.loadAsciiString()
            param['name'] = name[0]
            # No setter; the kernel looks the parameter up by name when non-zero, by short name path when zero
            param['is_name'] = bool(stream.loadOneByteType())
            common_loaders.put_map_entry(obj[key], positions, common_loaders.kernel_string_key(name), param)
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
