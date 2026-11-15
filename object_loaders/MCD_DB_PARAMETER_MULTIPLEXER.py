from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: getOffset
    obj['offset'] = stream.loadNumericType(4)
    
    obj['switch_key'] = DbObject.load_object_from_stream_if_exists(stream) # DbSwitchKey
    # kernel: fails when the cases are missing; kept readable for VW projects
    obj['cases'] = DbObject.load_object_from_stream_if_exists(stream) # DbCases
    obj['default_case'] = DbObject.load_object_from_stream_if_exists(stream) # DbDefaultCase
    
    return obj
