from common_utils import common_loaders
from object_loaders.MCD_DB_STATE_TRANSITION_ACTION import load_value_and_request_parameter


def load(stream):
    obj = {}
    
    # From database version 0018 on, a presence byte precedes the reference
    obj['diag_com_primitive'] = None
    if not stream.is_database_version_at_least(18) or stream.loadOneByteType():
        obj['diag_com_primitive'] = common_loaders.load_DbDiagComObjectReference(stream)
    
    obj.update(load_value_and_request_parameter(stream))
    
    # The table parameter reference lives in named stream C at the end of the enclosing
    # DB_STATE_CHART_DATA, which fills it in; read standalone it stays None
    obj['table_parameter'] = None
    
    return obj
