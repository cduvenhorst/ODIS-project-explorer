from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    
    obj['compu_method'] = DbObject.load_object_from_stream_if_exists(stream) # DbCompuMethod
    obj['diag_coded_type'] = DbObject.load_object_from_stream_if_exists(stream) # DbDiagCodedType
    obj['physical_type'] = DbObject.load_object_from_stream_if_exists(stream) # DbPhysicalType
    
    # kernel: std::map ordered by the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['physical_to_coded_index_map'] = []
    positions = {}
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        item['map_key'] = stream.loadNumericType(4)
        item['value'] = stream.loadNumericType(2)
        common_loaders.put_map_entry(obj['physical_to_coded_index_map'], positions, item['map_key'], item)

    # kernel: std::map ordered by the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['coded_to_physical_index_map'] = []
    positions = {}
    counter = stream.loadNumericType(2)
    for i in range(counter):
        item = {}
        item['map_key'] = stream.loadNumericType(4)
        item['value'] = stream.loadNumericType(2)
        common_loaders.put_map_entry(obj['coded_to_physical_index_map'], positions, item['map_key'], item)
    
    # kernel: the unit reference is set with setDbUnit
    obj['unit_reference'] = None
    if stream.loadOneByteType():
        obj['unit_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDDbUnitImpl
    
    obj['internal_constraint_reference'] = None
    if stream.loadOneByteType():
        obj['internal_constraint_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDConstraintImpl
    
    obj['physical_constraint_reference'] = None
    if stream.loadOneByteType():
        obj['physical_constraint_reference'] = common_loaders.load_reference(stream, False) # DbObjectReference : MCDConstraintImpl
    
    return obj
