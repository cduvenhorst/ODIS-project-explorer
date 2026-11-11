from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # No setter; non-zero selects a DbOdxLink instead of the reference
    obj['env_data_desc_dop_is_odx_link'] = bool(stream.loadOneByteType())
    obj['env_data_desc_dop_ref'] = None
    obj['env_data_desc_dop_odx_link'] = None
    if obj['env_data_desc_dop_is_odx_link']:
        obj['env_data_desc_dop_odx_link'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    else:
        obj['env_data_desc_dop_ref'] = common_loaders.load_reference(stream, False)
    
    obj['env_data'] = stream.loadAsciiString()[0]
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
