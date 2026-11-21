from classes import DbObject


def load(stream):
    obj = {}
    
    # items are special data elements and nested special data groups
    items = []
    for i in range(stream.loadNumericType(4)):
        items.append(DbObject.load_object_from_stream_if_exists(stream))
    obj['items'] = items
    
    caption_flag = stream.loadNumericType(1)
    if caption_flag == 0:
        obj['caption_reference'] = None
    elif caption_flag == 1:
        obj['caption_reference'] = {
            'object_key': stream.loadNumericType(4),
            'pool_id': stream.loadAsciiString()[0]
        }
    else:
        raise RuntimeError('Unknown caption flag: {}'.format(caption_flag))
    
    obj['semantic_information'] = stream.loadNativeAsciiString()
    
    return obj
