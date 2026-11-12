from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # The kernel uses the first name as short name only when session renaming is switched on,
    # otherwise the second; both are kept
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['odx_session_short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    
    obj['flash_pool_id'] = stream.loadAsciiString()[0]
    obj['checksums'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_CHECKSUMS
    obj['data_blocks'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_DATA_BLOCKS
    obj['expected_idents'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_IDENTS
    obj['flash_job_name'] = stream.loadAsciiString()[0]
    
    # No setter; name chosen for the flag, not taken from the kernel
    obj['has_flash_session_classes'] = bool(stream.loadOneByteType())
    obj['flash_session_classes'] = []
    if obj['has_flash_session_classes']:
        obj['flash_session_classes'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    obj['securities'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_FLASH_SECURITIES
    obj['flash_key'] = stream.loadAsciiString()[0]
    obj['priority'] = stream.loadNumericType(4)
    obj['is_download'] = bool(stream.loadOneByteType())
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_refs'] = []
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    return obj
