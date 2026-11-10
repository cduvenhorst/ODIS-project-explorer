from classes import DbObject
from common_utils import common_loaders


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
    obj['configuration_id'] = common_loaders.loadMCDValueFromObjectStream(stream)
    obj['has_configuration_id_item'] = bool(stream.loadOneByteType())
    obj['configuration_id_item'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbConfigurationIdItemImpl
    obj['has_data_id_item'] = bool(stream.loadOneByteType())
    obj['data_id_item'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbDataIdItemImpl
    
    # Named value-attributed references; no presence byte
    obj['data_record_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbValueAttributedObjectReference, 0)
    
    # Presence byte, then one value-attributed reference without a name
    obj['default_data_record_ref'] = None
    if stream.loadOneByteType():
        obj['default_data_record_ref'] = common_loaders.loadDbValueAttributedObjectReference(stream)
    
    obj['option_items'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbOptionItemsImpl
    obj['system_items'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbSystemItemsImpl
    obj['read_diag_com_primitives'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLinks
    obj['write_diag_com_primitives'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLinks
    obj['diag_com_data_connectors'] = DbObject.load_object_from_stream_if_exists(stream) # DbDiagComDataConnectors
    obj['configuration_record_value_size'] = stream.loadNumericType(4)
    obj['ecu_config_file_sub_dir_name'] = stream.loadAsciiString()[0]
    obj['parent_config_data_short_name'] = stream.loadAsciiString()[0]
    obj['disabled_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    obj['enabled_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    return obj
