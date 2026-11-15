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
    obj['configuration_record_references'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbValueAttributedObjectReference, 0)
    
    # kernel: below database version 0012 the key and the values are numbers, from 0012 ASCII strings
    # kernel: std::map ordered by the key (below 0012) or by the string number of the key (from 0012);
    # a later duplicate key replaces the earlier entry; kept in read order
    is_numeric = not stream.is_database_version_at_least(12)
    obj['base_variant_to_case_map'] = []
    positions = {}
    map_items = stream.loadNumericType(4)
    for i in range(map_items):
        entry = {}
        key = stream.loadNumericType(4) if is_numeric else stream.loadAsciiString()
        entry['map_key'] = key if is_numeric else key[0]
        entry['unknown_1'] = stream.loadEnumSmallRange()
        # kernel: std::set ordered by the value; a later duplicate value is dropped; kept in read order
        entry['values'] = []
        seen = set()
        collection_items = stream.loadNumericType(4)
        for j in range(collection_items):
            value = stream.loadNumericType(4) if is_numeric else stream.loadAsciiString()
            common_loaders.add_set_value(entry['values'], seen, value if is_numeric else common_loaders.kernel_string_key(value), value if is_numeric else value[0])
        common_loaders.put_map_entry(obj['base_variant_to_case_map'], positions, key if is_numeric else common_loaders.kernel_string_key(key), entry)
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_references'] = []
    if stream.loadOneByteType():
        obj['special_data_group_references'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['major'] = stream.loadNumericType(4)
    obj['minor'] = stream.loadNumericType(4)
    obj['revision'] = stream.loadNumericType(4)
    obj['is_revision_label_available'] = bool(stream.loadOneByteType())
    obj['additional_audience_refs'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    return obj
