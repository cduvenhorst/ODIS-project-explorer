from classes import DbObject


def load(stream):
    obj = {}
    
    # kernel: fails when the interval is missing; kept readable for VW projects
    obj['interval'] = DbObject.load_object_from_stream_if_exists(stream) # MCDIntervalImpl
    # kernel: fails when the scale constraints are missing; kept readable for VW projects
    obj['scale_constraints'] = DbObject.load_object_from_stream_if_exists(stream) # MCDScaleConstraintsImpl
    
    obj['is_computed'] = bool(stream.loadOneByteType())
    
    return obj
