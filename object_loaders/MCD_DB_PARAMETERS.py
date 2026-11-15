from classes import DbObject


def load(stream):
    obj = []
    
    counter = stream.loadNumericType(2)
    for i in range(counter):
        # kernel: fails when an element is empty; kept readable for VW projects; covers the request and the response parameters
        obj.append(DbObject.load_object_from_stream_if_exists(stream)) # MCDDbParameterImpl
    
    return obj
