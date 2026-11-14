from common_utils import common_loaders


def load(stream):
    obj = {}
    
    num = stream.loadNumericType(2)
    loop_index_less_than_num = (num != 0)
    
    # kernel: setProtStackMap; the key of each entry is the short name of the protocol stack
    obj['prot_stack_map'] = []
    loop_index = 0
    while True:
        if not loop_index_less_than_num:
            return obj
        
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        
        item['request_parameters_refs'] = []
        counter = stream.loadNumericType(2)
        for i in range(counter):
            ref = common_loaders.load_reference(stream, False, False) # DbObjectReference : MCDDbRequestParametersImpl
            item['request_parameters_refs'].append(ref)
        
        obj['prot_stack_map'].append(item)
        
        loop_index += 1
        loop_index_less_than_num = (loop_index < num)
