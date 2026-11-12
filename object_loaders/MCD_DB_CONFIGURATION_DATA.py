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
    
    # Named value-attributed references; no presence byte
    obj['configuration_record_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbValueAttributedObjectReference, 0)
    
    # kernel: below database version 0012 the key and the values are numbers, from 0012 ASCII strings
    is_numeric = not stream.is_database_version_at_least(12)
    obj['base_var_to_case_map'] = []
    map_items = stream.loadNumericType(4)
    for i in range(map_items):
        entry = {}
        entry['map_key'] = stream.loadNumericType(4) if is_numeric else stream.loadAsciiString()[0]
        entry['unknown_1'] = stream.loadEnumSmallRange()
        entry['values'] = []
        collection_items = stream.loadNumericType(4)
        for j in range(collection_items):
            entry['values'].append(stream.loadNumericType(4) if is_numeric else stream.loadAsciiString()[0])
        obj['base_var_to_case_map'].append(entry)
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['major'] = stream.loadNumericType(4)
    obj['minor'] = stream.loadNumericType(4)
    obj['revision'] = stream.loadNumericType(4)
    obj['is_revision_label_available'] = bool(stream.loadOneByteType())
    obj['additional_audience_refs'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    return obj
