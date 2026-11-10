from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['vehicle_information_refs'] = common_loaders.loadStringToReferenceMap(stream)
    
    # BaseVarProtIdToLinkInfoMap
    obj['base_var_prot_id_to_link_info_map'] = []
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        item['map_key'] = stream.loadAsciiString()[0]
        item['value'] = stream.loadAsciiString()[0]
        obj['base_var_prot_id_to_link_info_map'].append(item)
    
    return obj
