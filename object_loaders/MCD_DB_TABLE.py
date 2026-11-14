from common_utils import common_loaders


def load(stream):
    obj = {}
    
    # kernel: the name block starts with description id, long name id and unique object id
    obj['description_id'] = stream.loadAsciiString()[0]
    
    obj['long_name_id'] = stream.loadAsciiString()[0]
    
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    obj['table_key_map'] = []
    counter = stream.loadNumericType(4)
    for i in range(counter):
        item = {}
        
        # kernel: may fail when a row key cannot be resolved (unverified); kept readable for VW projects
        item['map_key'] = stream.loadUnicodeString()[0]
        
        # DbNamedObjectReference : MCDDbTableParameterImpl
        # kernel: the third word is read as object_id2, as in a reference with a third string
        item['reference'] = common_loaders.load_reference(stream, True)
        
        obj['table_key_map'].append(item)
    
    obj['semantic'] = stream.loadAsciiString()[0]
    
    # kernel: setDbDiagComPrimitives
    # MCDDbDiagComObjectReferences : DbDiagComObjectReference, MCDDbDiagComPrimitives, MCDDbDiagComPrimitive, MCDDbDiagComPrimitiveImpl
    obj['diag_com_primitives_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_DbDiagComObjectReference)
    
    if stream.loadOneByteType():
        obj['dop_simple_ref'] = common_loaders.load_reference(stream, False, False) # DbObjectReference : DbDopSimple
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_refs'] = []
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    return obj
