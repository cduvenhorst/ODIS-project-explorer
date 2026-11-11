from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # No setter; non-zero selects a DbOdxLink instead of the reference
    obj['dtc_dop_is_odx_link'] = bool(stream.loadOneByteType())
    obj['dtc_dop_ref'] = None
    obj['dtc_dop_odx_link'] = None
    if obj['dtc_dop_is_odx_link']:
        obj['dtc_dop_odx_link'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    else:
        obj['dtc_dop_ref'] = common_loaders.load_reference(stream, False)
    
    obj['diag_trouble_code'] = stream.loadAsciiString()[0]
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
