from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    # Semantically attributed references without a presence byte
    obj['source_state'] = common_loaders.loadDbAttributedObjectReference(stream)
    obj['target_state'] = common_loaders.loadDbAttributedObjectReference(stream)
    
    obj['has_external_access_method'] = bool(stream.loadOneByteType())
    if obj['has_external_access_method']:
        obj['external_access_method'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbExternalAccessMethodImpl
    else:
        obj['external_access_method'] = None
    
    return obj
