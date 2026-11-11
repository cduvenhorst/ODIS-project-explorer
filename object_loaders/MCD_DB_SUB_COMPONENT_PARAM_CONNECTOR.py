from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['diag_com_primitive_name'] = stream.loadAsciiString()[0]
    
    for key in ('sub_component_in_param_names', 'sub_component_out_param_names'):
        obj[key] = []
        param_count = stream.loadNumericType(2)
        for i in range(param_count):
            param = {}
            param['name'] = stream.loadAsciiString()[0]
            # No setter; the kernel looks the parameter up by name when non-zero, by short name path when zero
            param['is_name'] = bool(stream.loadOneByteType())
            obj[key].append(param)
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
