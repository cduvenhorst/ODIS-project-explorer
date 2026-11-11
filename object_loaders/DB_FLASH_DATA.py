from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['ecu_mem_refs'] = common_loaders.loadStringToReferenceMap(stream)
    
    return obj
