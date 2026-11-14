from common_utils import common_loaders
from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: the type code written by the read routine goes to the output side and
    # consumes no byte of the stream
    obj.update(common_loaders.loadStandardNameBlock(stream))
    
    # kernel: fails when the external access method is empty or the value exceeds 10;
    # kept readable for VW projects
    obj['external_access_method'] = stream.loadAsciiString()[0]
    obj['access_level_value'] = stream.loadNumericType(4)
    
    # kernel: cannot read a present diag com primitive; kept readable for VW projects
    obj['access_diag_com_primitive'] = DbObject.load_object_from_stream_if_exists(stream)
    
    return obj
