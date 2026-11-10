from common_utils import common_loaders, enum_converters
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    
    obj['description_id'] = stream.loadAsciiString()[0]
    
    obj['response_parameters'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbResponseParametersImpl
    
    obj['response_type'] = enum_converters.get_MCDResponseType(stream.loadEnumMediumRange())
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    return obj
