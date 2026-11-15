from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: setEnvDataDescDop(DbOdxLink); the byte only selects the branch
    is_odx_link = bool(stream.loadOneByteType())
    obj['env_data_desc_dop_reference'] = None
    obj['env_data_desc_dop'] = None
    if is_odx_link:
        # kernel: fails when the ODX link is missing; kept readable for VW projects
        obj['env_data_desc_dop'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    else:
        obj['env_data_desc_dop_reference'] = common_loaders.load_reference(stream, False)
    
    obj['env_data'] = stream.loadAsciiString()[0]
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
