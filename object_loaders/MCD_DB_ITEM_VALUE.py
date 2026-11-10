from classes import DbObject
from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['key'] = stream.loadAsciiString()[0]
    obj['meaning'] = stream.loadAsciiString()[0]
    obj['meaning_id'] = stream.loadAsciiString()[0]
    obj['physical_constant_value'] = stream.loadUnicodeString()[0]
    obj['rule'] = stream.loadAsciiString()[0]
    
    # DisabledAdditionalAudiences, EnabledAdditionalAudiences: presence byte, then named references
    obj['disabled_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    obj['enabled_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    return obj
