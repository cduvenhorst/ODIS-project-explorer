from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: fails when the matching parameters are missing; kept readable for VW projects
    obj['matching_parameters'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbMatchingParametersImpl
    
    return obj
