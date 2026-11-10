def load(stream):
    obj = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    
    obj['description_id'] = stream.loadAsciiString()[0] # DescriptionID; not always empty
    
    obj['length_exponent'] = stream.loadNumericType(4, True)
    obj['mass_exponent'] = stream.loadNumericType(4, True)
    obj['time_exponent'] = stream.loadNumericType(4, True)
    obj['current_exponent'] = stream.loadNumericType(4, True)
    obj['temperature_exponent'] = stream.loadNumericType(4, True)
    obj['molar_amount_exponent'] = stream.loadNumericType(4, True)
    obj['luminous_intensity_exponent'] = stream.loadNumericType(4, True)
    
    return obj
