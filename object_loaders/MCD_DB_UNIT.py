from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    
    obj['description_id'] = stream.loadAsciiString()[0] # DescriptionID; not always empty
    
    obj['display_name'] = stream.loadUnicodeString()[0]
    
    obj['factor_si_to_unit'] = stream.loadDoubleType()
    obj['offset_si_to_unit'] = stream.loadDoubleType()
    
    obj['physical_dimension'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbPhysicalDimensionImpl
    
    obj['unit_group_refs'] = None
    if stream.loadOneByteType():
        obj['unit_group_refs'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)
    
    return obj
