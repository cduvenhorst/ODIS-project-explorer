from classes import DbObject
from common_utils import common_loaders


def _load_audiences(stream):
    # Presence byte, then named references
    if stream.loadOneByteType():
        return common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    return None


def load(stream):
    obj = {}
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    obj['audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    obj['binary_data'] = common_loaders.loadBytefieldFromObjectStream(stream)
    obj['data_format'] = stream.loadEnumMediumRange() # MCDFlashDataFormat
    obj['data_id'] = common_loaders.loadMCDValueFromObjectStream(stream)
    
    # The object follows its own presence byte, independent of this flag
    obj['has_coding_data'] = bool(stream.loadOneByteType())
    obj['coding_data'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbCodingDataImpl
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['key'] = stream.loadAsciiString()[0]
    obj['rule'] = stream.loadAsciiString()[0]
    obj['configuration_record_value_size'] = stream.loadNumericType(4)
    obj['parent_config_data_short_name'] = stream.loadAsciiString()[0]
    obj['disabled_additional_audiences'] = _load_audiences(stream)
    obj['enabled_additional_audiences'] = _load_audiences(stream)
    
    return obj
