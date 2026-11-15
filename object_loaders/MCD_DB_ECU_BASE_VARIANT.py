from common_utils import common_loaders
from object_loaders import MCD_DB_ECU
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['ecu_variant_references'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    # kernel: two parallel vectors are filled in stream order, the variant name and its pattern
    # collection; the key is the short name of a variant
    obj['ecu_variant_patterns'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        item['ecu_variant_patterns'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbMatchingPatternsImpl
        
        obj['ecu_variant_patterns'].append(item)
    
    # kernel: the MCDDbEcuImpl part is read into the same object
    obj.update(MCD_DB_ECU.load(stream))
    
    return obj
