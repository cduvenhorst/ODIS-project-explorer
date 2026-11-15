from common_utils import common_loaders


def load(stream):
    obj = {}
    
    num = stream.loadNumericType(2)
    loop_index_less_than_num = (num != 0)
    
    # kernel: setProtStackMap; the key of each entry is the short name of the protocol stack
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    obj['protocol_stack_map'] = []
    positions = {}
    loop_index = 0
    while True:
        if not loop_index_less_than_num:
            return obj
        
        item = {}
        
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        
        item['request_parameters_references'] = []
        counter = stream.loadNumericType(2)
        for i in range(counter):
            ref = common_loaders.load_reference(stream, False) # DbObjectReference : MCDDbRequestParametersImpl
            item['request_parameters_references'].append(ref)
        
        common_loaders.put_map_entry(obj['protocol_stack_map'], positions, common_loaders.kernel_string_key(key), item)
        
        loop_index += 1
        loop_index_less_than_num = (loop_index < num)
