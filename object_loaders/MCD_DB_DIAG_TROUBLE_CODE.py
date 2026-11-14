from common_utils import common_loaders


def load(stream):
    obj = {}
    
    # kernel: the string sits where the name block keeps the unique object identifier
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['short_name'] = stream.loadAsciiString()[0]
    # kernel: setDisplayTroubleCode / getDisplayTroubleCode
    obj['display_trouble_code'] = stream.loadAsciiString()[0]
    # kernel: setDTCText / getDTCText
    obj['dtc_text'] = stream.loadUnicodeString()[0]
    
    obj['level'] = stream.loadNumericType(4)
    
    obj['trouble_code'] = stream.loadNumericType(4)
    
    # kernel: an absent collection reads as an empty one
    obj['special_data_group_refs'] = []
    if stream.loadOneByteType():
        obj['special_data_group_refs'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    # kernel: setDiagTroubleCodeTextID / getDiagTroubleCodeTextID
    obj['diag_trouble_code_text_id'] = stream.loadAsciiString()[0]
    
    return obj
