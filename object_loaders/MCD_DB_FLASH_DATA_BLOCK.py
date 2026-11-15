from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    obj['address_offset'] = stream.loadNumericType(8)
    obj['data_block_type'] = stream.loadAsciiString()[0]
    obj['flash_data'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_DATA
    obj['flash_filters'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_FILTERS
    obj['flash_segments'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_SEGMENTS
    obj['own_idents'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_IDENTS
    obj['securities'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_SECURITIES
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_references'] = []
    if stream.loadOneByteType():
        obj['special_data_group_references'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    # kernel: stores this as a flag set by setLogicalBlockIndex; the getter reports not set without it
    obj['has_logical_block_index'] = bool(stream.loadOneByteType())
    obj['logical_block_index'] = None
    if obj['has_logical_block_index']:
        obj['logical_block_index'] = stream.loadNumericType(4)
    
    obj['audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_AUDIENCE
    obj['disabled_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    obj['enabled_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    return obj
