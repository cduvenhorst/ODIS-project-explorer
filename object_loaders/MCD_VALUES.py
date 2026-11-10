from common_utils import common_loaders


def load(stream):
    obj = []
    
    for i in range(stream.loadNumericType(2)):
        obj.append(common_loaders.loadMCDValueFromObjectStream(stream))
    
    return obj
