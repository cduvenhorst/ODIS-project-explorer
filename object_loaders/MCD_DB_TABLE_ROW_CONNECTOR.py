from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: setDbTable(DbOdxLink); the byte only selects the branch
    is_odx_link = bool(stream.loadOneByteType())
    obj['table_reference'] = None
    obj['table'] = None
    if is_odx_link:
        # kernel: fails when the ODX link is missing; kept readable for VW projects
        obj['table'] = DbObject.load_object_from_stream_if_exists(stream) # DbOdxLink
    else:
        obj['table_reference'] = common_loaders.loadDbAttributedObjectReference(stream)
    
    obj['table_row'] = stream.loadAsciiString()[0]
    
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    return obj
