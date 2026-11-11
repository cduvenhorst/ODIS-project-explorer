from common_utils import common_loaders


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    obj['filter_start'] = stream.loadNumericType(4)
    obj['filter_end'] = stream.loadNumericType(4)
    obj['filter_size'] = stream.loadNumericType(4)
    
    return obj
