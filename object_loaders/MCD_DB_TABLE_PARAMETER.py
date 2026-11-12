from object_loaders import MCD_DB_PARAMETER
from classes import DbObject
from common_utils import common_loaders

# Named streams, as the kernel reads them: A = IsApiExecutable (1 byte),
# B = PreConditionStates (named attributed references).
NAMED_STREAM_READERS = {
    'A': lambda stream: bool(stream.loadOneByteType()),
    'B': lambda stream: common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(
        stream, common_loaders.loadDbAttributedObjectReference),
}


def load(stream):
    obj = {}
    
    obj['key'] = stream.loadUnicodeString()[0]
    
    obj['audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    
    # DisabledAdditionalAudiences, EnabledAdditionalAudiences: presence byte, then named references
    # kernel: an absent collection reads as an empty one
    obj['disabled_additional_audiences'] = []
    if stream.loadOneByteType():
        obj['disabled_additional_audiences'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    # kernel: an absent collection reads as an empty one
    obj['enabled_additional_audiences'] = []
    if stream.loadOneByteType():
        obj['enabled_additional_audiences'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    obj['parameter'] = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER'}
    obj['parameter'].update(MCD_DB_PARAMETER.load(stream))
    
    streams = common_loaders.loadNamedStreams(stream, NAMED_STREAM_READERS)
    obj['is_api_executable'] = streams.get('A', True)
    obj['pre_condition_state_refs'] = streams.get('B')
    
    return obj
