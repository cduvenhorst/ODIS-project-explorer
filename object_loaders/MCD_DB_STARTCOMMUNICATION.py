from common_utils import common_loaders
from object_loaders import MCD_DB_DIAG_COM_PRIMITIVE


def load(stream):
    obj = MCD_DB_DIAG_COM_PRIMITIVE.load(stream) # super = MCDDbDiagComPrimitiveImpl
    
    # kernel: each entry carries an optional parameters object, as in MCD_DB_DIAG_SERVICE; fixed: upstream skipped the parameters object
    obj['service_protocol_parameters'] = common_loaders.loadServiceProtocolParametersMap(stream)
    
    return obj
