from common_utils import common_loaders


def load(stream):
    obj = {}
    
    # kernel: setDbVehicleInfoRefs
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['vehicle_information_references'] = common_loaders.loadStringToReferenceMap(stream)
    
    # BaseVarProtIdToLinkInfoMap
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['base_variant_protocol_id_to_link_information_map'] = []
    positions = {}
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        item['value'] = stream.loadAsciiString()[0]
        common_loaders.put_map_entry(obj['base_variant_protocol_id_to_link_information_map'], positions, common_loaders.kernel_string_key(key), item)
    
    return obj
