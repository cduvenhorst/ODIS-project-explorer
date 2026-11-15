from common_utils import common_loaders


def load(stream):
    obj = {}
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['ecu_mem_references'] = common_loaders.loadStringToReferenceMap(stream)
    
    return obj
