from common_utils import common_loaders


def load(stream):
    obj = {}
    
    obj['code_file'] = stream.loadUnicodeString()[0]
    obj['encryption'] = stream.loadUnicodeString()[0]
    obj['syntax'] = stream.loadUnicodeString()[0]
    obj['revision'] = stream.loadUnicodeString()[0]
    obj['entry_point'] = stream.loadUnicodeString()[0]
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['library_references'] = common_loaders.loadStringToReferenceMap(stream, is_three_word_reference=True)
        
    return obj
