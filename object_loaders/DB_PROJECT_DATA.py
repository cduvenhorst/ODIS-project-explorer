from common_utils import common_loaders
from object_loaders import MCD_DB_LOCATION_REFERENCES
from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: setLocationMap; std::map ordered by the number of the access key string; a later duplicate key replaces the earlier entry; kept in read order
    obj['location_map'] = []
    positions = {}
    counter = stream.loadNumericType(2)
    for i in range(counter):
        entry = MCD_DB_LOCATION_REFERENCES.load(stream)
        access_key = entry['access_key']
        key_string = access_key['string'] if access_key is not None else None
        if key_string is None:
            # kernel: fails when a location has no access key; kept readable for VW projects
            obj['location_map'].append(entry)
        else:
            common_loaders.put_map_entry(obj['location_map'], positions, key_string, entry)
    
    obj['functional_group_reference'] = common_loaders.load_reference(stream)
    # kernel: setBaseVariantRef
    obj['base_variant_reference'] = common_loaders.load_reference(stream)
    # kernel: setEcuVariantRefs
    obj['ecu_variant_references'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    obj['ecu_variant_reference'] = common_loaders.load_reference(stream)
    
    # kernel: setContainerShortName, setLayerShortName and setLayerID
    obj['container_short_name'] = stream.loadAsciiString()[0]
    obj['layer_short_name'] = stream.loadAsciiString()[0]
    obj['layer_id'] = stream.loadAsciiString()[0]
    
    # kernel: setFuncGroupParentPoolIds
    obj['functional_group_parent_pool_ids'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    
    # kernel: setEcuVarProjects; the elements are the project data of the variants
    obj['ecu_variant_projects'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        # kernel: fails when an element is not project data; kept readable for VW projects
        obj['ecu_variant_projects'].append(DbObject.load_object_from_stream_if_exists(stream))
    
    return obj
