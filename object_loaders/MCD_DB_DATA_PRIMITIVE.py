from common_utils import common_loaders
from common_utils import enum_converters
from object_loaders import MCD_DB_DIAG_COM_PRIMITIVE
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['access_level'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbAccessLevelImpl
    obj['audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    
    # kernel: an unknown repetition mode is kept as its number
    obj['repetition_mode'] = enum_converters.enum_name_or_number(enum_converters.get_MCDRepetitionMode, 0x6600 + stream.loadNumericType(1))
    
    obj['related_data_primitives'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_DbDiagComObjectReference) # MCDDbDiagComObjectReferences : DbDiagComObjectReference, MCDDbDataPrimitives, MCDDbDataPrimitive, MCDDbDataPrimitiveImpl
    
    status_byte = stream.loadNumericType(1)
    
    # kernel: an absent collection reads as an empty one
    obj['disabled_additional_audiences'] = []
    if status_byte & 1:
        obj['disabled_additional_audiences'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    # kernel: an absent collection reads as an empty one
    obj['enabled_additional_audiences'] = []
    if status_byte & 2:
        obj['enabled_additional_audiences'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_references'] = []
    if status_byte & 4:
        obj['special_data_group_references'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    # kernel: the MCDDbDiagComPrimitiveImpl part is read into the same object
    obj.update(MCD_DB_DIAG_COM_PRIMITIVE.load(stream))
    
    return obj
