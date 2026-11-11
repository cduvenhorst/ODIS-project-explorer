from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    # Name derived from the byte's position; the kernel has no getter for it
    obj['has_layers'] = bool(stream.loadOneByteType())
    obj['base_variants'] = None
    obj['variants'] = None
    obj['layers'] = None
    obj['all_variant_layers'] = None
    if obj['has_layers']:
        obj['layers'] = DbObject.load_object_from_stream_if_exists(stream) # DB_ODX_LINKS
        obj['all_variant_layers'] = DbObject.load_object_from_stream_if_exists(stream)
    else:
        obj['base_variants'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
        obj['variants'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    obj['flash_sessions'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbAttributedObjectReference)
    obj['additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    # Name derived from the byte's position; the kernel has no getter for it
    obj['has_flash_session_classes'] = bool(stream.loadOneByteType())
    obj['flash_session_class_refs'] = None
    if obj['has_flash_session_classes']:
        obj['flash_session_class_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    # Name derived from the byte's position; the kernel reads the state through hasPhysicalMemory
    obj['has_physical_memory'] = bool(stream.loadOneByteType())
    obj['physical_memory_ref'] = None
    if obj['has_physical_memory']:
        obj['physical_memory_ref'] = common_loaders.loadDbAttributedObjectReference(stream)
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    return obj
