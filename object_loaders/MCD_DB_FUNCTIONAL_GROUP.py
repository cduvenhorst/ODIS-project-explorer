from common_utils import common_loaders
from object_loaders import MCD_DB_ECU


def load(stream):
    obj = {}
    
    # kernel: setGroupMembers
    obj['group_member_references'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    # kernel: the MCDDbEcuImpl part is read into the same object
    obj.update(MCD_DB_ECU.load(stream))
    
    return obj
