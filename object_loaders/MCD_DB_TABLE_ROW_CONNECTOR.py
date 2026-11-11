from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # No setter; non-zero selects a DbOdxLink instead of the reference
    obj['table_is_odx_link'] = bool(stream.loadOneByteType())
    obj['table_ref'] = None
    obj['table_odx_link'] = None
    if obj['table_is_odx_link']:
        obj['table_odx_link'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    else:
        obj['table_ref'] = common_loaders.loadDbAttributedObjectReference(stream)
    
    obj['table_row'] = stream.loadAsciiString()[0]
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
