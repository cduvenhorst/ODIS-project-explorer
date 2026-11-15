from common_utils import common_loaders


def load(stream):
    obj = {}
    
    # kernel: setDbVehicleInfoRefs
    obj['vehicle_information_references'] = common_loaders.loadStringToReferenceMap(stream)
    
    # BaseVarProtIdToLinkInfoMap
    obj['base_variant_protocol_id_to_link_information_map'] = []
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        item['map_key'] = stream.loadAsciiString()[0]
        item['value'] = stream.loadAsciiString()[0]
        obj['base_variant_protocol_id_to_link_information_map'].append(item)
    
    return obj
