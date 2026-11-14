from common_utils import common_loaders
from object_loaders import MCD_DB_LOCATION_REFERENCES
from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: setLocationMap
    obj['location_map'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        obj['location_map'].append(MCD_DB_LOCATION_REFERENCES.load(stream))
    
    obj['functional_group_ref'] = common_loaders.load_reference(stream)
    # kernel: setBaseVariantRef
    obj['base_variant_ref'] = common_loaders.load_reference(stream)
    # kernel: setEcuVariantRefs
    obj['ecu_variant_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    obj['ecu_variant_ref'] = common_loaders.load_reference(stream)
    
    # kernel: setContainerShortName, setLayerShortName and setLayerID
    obj['container_short_name'] = stream.loadAsciiString()[0]
    obj['layer_short_name'] = stream.loadAsciiString()[0]
    obj['layer_id'] = stream.loadAsciiString()[0]
    
    # kernel: setFuncGroupParentPoolIds
    obj['func_group_parent_pool_ids'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    
    # kernel: setEcuVarProjects; the elements are the project data of the variants
    obj['ecu_var_projects'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        # kernel: fails when an element is not project data; kept readable for VW projects
        obj['ecu_var_projects'].append(DbObject.load_object_from_stream_if_exists(stream))
    
    return obj
