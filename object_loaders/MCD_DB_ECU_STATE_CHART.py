from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    # no setter; named after the proxy getter getSemantic
    obj['semantic'] = stream.loadAsciiString()[0]
    obj['ecu_states'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbAttributedObjectReference)
    # short name of the start state, looked up in ecu_states
    obj['start_state'] = stream.loadAsciiString()[0]
    obj['ecu_state_transitions'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbAttributedObjectReference)
    
    return obj
