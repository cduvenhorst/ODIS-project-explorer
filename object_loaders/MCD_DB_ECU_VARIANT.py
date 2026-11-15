from common_utils import common_loaders
from object_loaders import MCD_DB_ECU
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['ecu_base_variant_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDDbEcuBaseVariantImpl
    
    # kernel: setDbVariantPatterns
    obj['variant_patterns'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbMatchingPatternsImpl
    
    obj['ecu'] = {'#OBJECT_TYPE': 'MCD_DB_ECU'}
    obj['ecu'].update(MCD_DB_ECU.load(stream))
    
    return obj
