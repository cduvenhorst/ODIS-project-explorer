from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # DescriptionID, LongNameID and UniqueObjectIdentifier; not always empty
    obj['description_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    
    obj['description'] = stream.loadUnicodeString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['short_name'] = stream.loadAsciiString()[0]
    
    obj['diag_trouble_code_connectors'] = DbObject.load_object_from_stream_if_exists(stream)
    obj['env_data_connectors'] = DbObject.load_object_from_stream_if_exists(stream)
    obj['sub_component_param_connectors'] = DbObject.load_object_from_stream_if_exists(stream)
    obj['sub_component_patterns'] = DbObject.load_object_from_stream_if_exists(stream)
    obj['table_row_connectors'] = DbObject.load_object_from_stream_if_exists(stream)
    
    # No setter; named after the kernel getter
    obj['semantic'] = stream.loadAsciiString()[0]
    
    obj['dtc_dop_names'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    obj['dtc_names'] = common_loaders.loadAsciiStringVectorFromObjectStream(stream)
    
    return obj
