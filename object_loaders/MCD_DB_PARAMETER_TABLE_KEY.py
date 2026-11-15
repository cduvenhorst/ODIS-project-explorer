from common_utils import common_loaders
from object_loaders import MCD_DB_PARAMETER
from classes import DbObject


def load(stream):
    obj = MCD_DB_PARAMETER.load(stream) # super = MCDDbParameterImpl
    
    obj['table'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbTableImpl
    
    # kernel: getDbTableRefAsSharedPtr reports 'table reference not set' when a table object came instead
    obj['table_reference'] = None
    if obj['table'] is None:
        obj['table_reference'] = common_loaders.loadDbAttributedObjectReference(stream) # DbAttributedObjectReference : MCDDbTableImpl
    
    obj['is_table_row_reference'] = bool(stream.loadOneByteType())
    
    # kernel: setRowRefShortName
    obj['row_reference_short_name'] = stream.loadAsciiString()[0]
    
    return obj
