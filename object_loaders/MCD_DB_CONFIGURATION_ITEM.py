# Common base MCDDbConfigurationItemImpl of option, system and identifier items; not registered, the kernel has no factory entry for this type
from classes import DbObject
from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_refs'] = []
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['parameter'] = DbObject.load_object_from_stream_if_exists(stream) # setDbParameter; MCDDbParameterSimple in the data
    obj['is_complex'] = bool(stream.loadOneByteType())
    
    return obj
