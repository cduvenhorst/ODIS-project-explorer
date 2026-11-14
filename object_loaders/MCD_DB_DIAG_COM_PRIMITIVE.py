from common_utils import common_loaders
from common_utils import enum_converters


def load(stream):
    obj = {}
    
    obj['description_id'] = stream.loadAsciiString()[0] # DescriptionID; not always empty
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    if stream.loadOneByteType():
        obj['request_ref'] = common_loaders.load_reference(stream, False, False) # DbObjectReference : MCDDbRequestImpl
    
    # kernel: setDbPositiveResponses, setDbNegativeResponses, setDbFunctionalClasses
    obj['positive_response_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    obj['negative_response_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    obj['functional_class_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    obj['semantic'] = stream.loadAsciiString()[0]
    
    # kernel: an unknown transmission mode is kept as its number by the setter
    obj['transmission_mode'] = enum_converters.enum_name_or_number(enum_converters.get_MCDTransmissionMode, stream.loadEnumMediumRange())
    
    obj['is_api_executable'] = bool(stream.loadOneByteType())
    # kernel: setIsNoOperation (fixed: upstream misspelt the key)
    obj['is_no_operation'] = bool(stream.loadOneByteType())
    
    obj['diagnostic_class'] = stream.loadEnumSmallRange()
    
    # kernel: setDbEcuStateTransitions
    # DbNamedObjectReferences - DbSemanticAttributedObjectReference - MCDDbEcuStateTransitionImpl
    obj['ecu_state_transition_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(
        stream, common_loaders.loadDbAttributedObjectReference)
    # Elements are DbSemanticAttributedObjectReference
    
    # kernel: setDbEcuStates
    # DbNamedObjectReferences - DbSemanticAttributedObjectReference - MCDDbEcuStateImpl
    obj['ecu_state_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(
        stream, common_loaders.loadDbAttributedObjectReference)
    # Elements are DbSemanticAttributedObjectReference
    
    obj['has_suppress_positive_response_capability'] = bool(stream.loadOneByteType())
    
    if obj['has_suppress_positive_response_capability']:
        # kernel: setPosRespSuppressBitMask, setPosRespSuppressParamSNPath and
        # setPosRespSuppressParamShortName; both names are always present, the one not read is None
        obj['pos_resp_suppress_bit_mask'] = common_loaders.loadBytefieldFromObjectStream(stream)
        
        obj['has_pos_resp_suppress_param_sn_path'] = bool(stream.loadOneByteType())
        obj['pos_resp_suppress_param_sn_path'] = None
        obj['pos_resp_suppress_param_short_name'] = None
        if obj['has_pos_resp_suppress_param_sn_path']:
            obj['pos_resp_suppress_param_sn_path'] = stream.loadAsciiString()[0]
        else:
            obj['pos_resp_suppress_param_short_name'] = stream.loadAsciiString()[0]
    
    return obj
