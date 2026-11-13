from common_utils import common_loaders
from object_loaders import MCD_DB_PARAMETER
from classes import DbObject


def load(stream):
    obj = MCD_DB_PARAMETER.load(stream) # super = MCDDbParameterImpl
    
    obj['table'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbTableImpl
    
    if obj['table'] is None:
        obj['table_ref'] = common_loaders.loadDbAttributedObjectReference(stream) # DbAttributedObjectReference : MCDDbTableImpl
    
    obj['is_table_row_reference'] = bool(stream.loadOneByteType())
    
    # kernel: short name of the referenced table row
    obj['table_row_short_name'] = stream.loadAsciiString()[0]
    
    return obj
