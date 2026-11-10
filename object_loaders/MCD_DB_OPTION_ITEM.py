from object_loaders import MCD_DB_CONFIGURATION_ITEM
from classes import DbObject
from common_utils import common_loaders


def load(stream):
    obj = MCD_DB_CONFIGURATION_ITEM.load(stream)
    
    obj['item_values'] = DbObject.load_object_from_stream_if_exists(stream) # MCDDbItemValuesImpl
    obj['physical_default_value'] = stream.loadUnicodeString()[0]
    obj['read_audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    obj['write_audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    obj['disabled_read_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    obj['enabled_read_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    obj['disabled_write_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    obj['enabled_write_additional_audiences'] = common_loaders.loadAdditionalAudiencesFromObjectStream(stream)
    
    return obj
