from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    obj['ident_values'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_VALUES
    obj['read_ident_description'] = DbObject.load_object_from_stream_if_exists(stream) # MCD_DB_IDENT_DESCRIPTION
    
    return obj
