from common_utils import common_loaders


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    # kernel: the values go to setFlashwareChecksum, setFlashwareSignature, setSecurityMethod and setValidity in this order
    obj['flashware_checksum'] = common_loaders.loadMCDValueFromObjectStream(stream)
    obj['flashware_signature'] = common_loaders.loadMCDValueFromObjectStream(stream)
    obj['security_method'] = common_loaders.loadMCDValueFromObjectStream(stream)
    obj['validity'] = common_loaders.loadMCDValueFromObjectStream(stream)
    
    return obj
