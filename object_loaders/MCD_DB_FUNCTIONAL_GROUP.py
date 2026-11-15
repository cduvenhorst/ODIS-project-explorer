from common_utils import common_loaders
from object_loaders import MCD_DB_ECU


def load(stream):
    obj = {}
    
    # kernel: setGroupMembers
    obj['group_member_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    obj['ecu'] = {'#OBJECT_TYPE': 'MCD_DB_ECU'}
    obj['ecu'].update(MCD_DB_ECU.load(stream))
    
    return obj
