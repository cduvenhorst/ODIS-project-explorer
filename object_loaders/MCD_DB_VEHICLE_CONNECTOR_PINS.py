from classes import DbObject


def load(stream):
    obj = []
    
    counter = stream.loadNumericType(2)
    for i in range(counter):
        # kernel: fails when an element is empty; kept readable for VW projects
        obj.append(DbObject.load_object_from_stream_if_exists(stream))
    
    return obj
