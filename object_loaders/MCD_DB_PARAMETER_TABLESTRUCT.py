from common_utils import common_loaders
from object_loaders import MCD_DB_PARAMETER


def load(stream):
    obj = MCD_DB_PARAMETER.load(stream) # super = MCDDbParameterImpl
    
    obj['key_parameter_short_name'] = stream.loadAsciiString()[0]
    obj['table_reference'] = common_loaders.loadDbAttributedObjectReference(stream) # DbAttributedObjectReference : MCDDbTableImpl
    
    return obj
