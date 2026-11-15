from common_utils import common_loaders


def load(stream):
    obj = {}
    
    val = stream.loadOneByteType()
    if val == 0:
        # kernel: getDopStructure
        obj['dop_structure_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : DbDopStructure
    else:
        # kernel: getDopEnvDataDescRef
        obj['dop_env_data_desc_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : DbDopEnvDataDesc
    
    return obj
