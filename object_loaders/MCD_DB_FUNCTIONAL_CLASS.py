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
    
    # MCDDbDiagComObjectReferences : DbDiagComObjectReference, MCDDbDataPrimitives, MCDDbDataPrimitive, MCDDbDataPrimitiveImpl
    
    obj['data_primitive_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_DbDiagComObjectReference)
    
    return obj
