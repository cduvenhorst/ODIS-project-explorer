from object_loaders import MCD_DB_CONFIGURATION_ITEM


def load(stream):
    obj = MCD_DB_CONFIGURATION_ITEM.load(stream)
    
    obj['system_parameter_name'] = stream.loadAsciiString()[0]
    
    return obj
