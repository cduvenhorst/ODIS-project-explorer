from common_utils import common_loaders
from common_utils import enum_converters
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['layer_id'] = stream.loadAsciiString()[0]
    obj['layer_name'] = stream.loadAsciiString()[0]  # kernel: setLayerName
    obj['protocol_type'] = stream.loadAsciiString()[0]
    obj['protocol_stack_short_name'] = stream.loadAsciiString()[0]
    obj['com_param_spec_pool_id'] = stream.loadAsciiString()[0]
    
    obj['location_type'] = enum_converters.get_MCDLocationType(stream.loadEnumMediumRange())
    
    match obj['location_type']:
        case 'eECU_BASE_VARIANT':
            obj['base_variant_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDDbEcuBaseVariantImpl
        case 'eECU_VARIANT':
            obj['ecu_variant_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDDbEcuVariantImpl
        case 'eFUNCTIONAL_GROUP':
            obj['functional_group_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDDbFunctionalGroupImpl
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['diag_com_primitive_references'] = common_loaders.loadStringToReferenceMap(stream, is_DbDiagComObjectReference=True)
    
    obj['dtc_dop_names'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['dop_references'] = common_loaders.loadStringToReferenceMap(stream)
    # kernel: DbSemanticAttributedObjectReference, read as an attributed reference
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['table_references'] = common_loaders.loadStringToReferenceMap(stream, is_attributed_reference=True)
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['request_references'] = common_loaders.loadStringToReferenceMap(stream)
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['global_negative_response_references'] = common_loaders.loadStringToReferenceMap(stream)
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['functional_class_references'] = common_loaders.loadStringToReferenceMap(stream)
    
    # kernel: setFunctClassDataPrimitivesMap; the entry's own map is the data primitives map
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['functional_class_data_primitives_map'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
        item['data_primitives_map'] = common_loaders.loadStringToReferenceMap(stream, is_DbDiagComObjectReference = True)
        
        obj['functional_class_data_primitives_map'].append(item)
    
    # kernel: DbSemanticAttributedObjectReference, read as an attributed reference
    # EcuStateChartRefs
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['ecu_state_chart_references'] = common_loaders.loadStringToReferenceMap(stream, is_attributed_reference=True)
    # SubComponentRefs
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['sub_component_references'] = common_loaders.loadStringToReferenceMap(stream, is_attributed_reference=True)
    # AdditionalAudienceRefs
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['additional_audience_references'] = common_loaders.loadStringToReferenceMap(stream)
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['env_data_descs'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        
        item['env_data_desc'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbEnvDataDescImpl
        
        obj['env_data_descs'].append(item)
    
    obj['parent_layers'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    obj['shared_data_parent_layers'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['not_inherited_dops'] = common_loaders.loadStringVectorMapFromObjectStream(stream)
    # NotInheritedTables
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['not_inherited_tables'] = common_loaders.loadStringVectorMapFromObjectStream(stream)
    # NotInheritedDiagComms
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['not_inherited_diag_com_primitives'] = common_loaders.loadStringVectorMapFromObjectStream(stream)
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['not_inherited_global_negative_responses'] = common_loaders.loadStringVectorMapFromObjectStream(stream)
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['unit_group_references'] = common_loaders.loadStringToReferenceMap(stream)
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['unit_references'] = common_loaders.loadStringToReferenceMap(stream)
    
    obj['layer_com_params'] = []
    counter = stream.loadNumericType(2)
    for i in range(counter):
        obj['layer_com_params'].append(DbObject.load_object_from_stream_if_exists(stream))
    
    # kernel: this byte is present unless the database version is 0015; it is not used
    if not stream.is_database_version(15):
        stream.loadOneByteType()
    
    # SpecialDataGroupRefs; kernel: an absent collection reads as an empty one
    obj['special_data_group_references'] = []
    if stream.loadOneByteType():
        obj['special_data_group_references'] = common_loaders.loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream)
    
    # MultipleEcuJobRefs
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['multiple_ecu_job_references'] = common_loaders.loadStringToReferenceMap(stream, is_DbDiagComObjectReference = True)
    
    return obj
