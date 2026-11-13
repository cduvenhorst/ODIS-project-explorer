from common_utils import common_loaders


def load(stream):
    obj = {}
    
    val = stream.loadOneByteType()
    if val == 0:
        # kernel: getDopStructure
        obj['dop_structure_ref'] = common_loaders.load_reference(stream, False, False) # DbObjectReference : DbDopStructure
    else:
        # kernel: getDopEnvDataDescRef
        obj['dop_env_data_desc_ref'] = common_loaders.load_reference(stream, False, False) # DbObjectReference : DbDopEnvDataDesc
    
    return obj
