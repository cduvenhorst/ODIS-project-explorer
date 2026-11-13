from object_loaders import DB_CASE_BASE
from classes import DbObject


def load(stream):
    obj = {}
    
    obj['lower_limit'] = DbObject.load_object_from_stream_if_exists(stream) # DbLimit
    obj['upper_limit'] = DbObject.load_object_from_stream_if_exists(stream) # DbLimit
    
    # kernel: a missing limit aborts loading
    if obj['lower_limit'] is None or obj['upper_limit'] is None:
        raise RuntimeError('DB_CASE needs a lower and an upper limit')
    
    obj.update(DB_CASE_BASE.load(stream)) # super = DbCaseBase
    
    return obj
