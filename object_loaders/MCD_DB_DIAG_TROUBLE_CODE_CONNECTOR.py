from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: setDtcDop(DbOdxLink); the byte only selects the branch
    is_odx_link = bool(stream.loadOneByteType())
    obj['dtc_dop_reference'] = None
    obj['dtc_dop'] = None
    if is_odx_link:
        # kernel: fails when the ODX link is missing; kept readable for VW projects
        obj['dtc_dop'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    else:
        obj['dtc_dop_reference'] = common_loaders.load_reference(stream, False)
    
    obj['diag_trouble_code'] = stream.loadAsciiString()[0]
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
