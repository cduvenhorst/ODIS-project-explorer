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
    
    # Named value-attributed references; no presence byte
    obj['configuration_record_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.loadDbValueAttributedObjectReference, 0)
    
    # The kernel reads key and values as numbers when a configuration value is below "0012"; it always saves ASCII
    obj['base_var_to_case_map'] = []
    for _ in range(stream.loadNumericType(4)):
        entry = {}
        entry['map_key'] = stream.loadAsciiString()[0]
        entry['unknown_1'] = stream.loadEnumSmallRange()
        entry['values'] = [stream.loadAsciiString()[0] for _ in range(stream.loadNumericType(4))]
        obj['base_var_to_case_map'].append(entry)
    
    obj['special_data_group_refs'] = None
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    obj['major'] = stream.loadNumericType(4)
    obj['minor'] = stream.loadNumericType(4)
    obj['revision'] = stream.loadNumericType(4)
    obj['is_revision_label_available'] = bool(stream.loadOneByteType())
    obj['additional_audience_refs'] = _load_audiences(stream)
    
    return obj
