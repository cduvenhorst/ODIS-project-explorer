# Helpers for the configuration data (MCD_DB_CONFIGURATION_DATA) of a project: listing them per pool
# and deciding which of them apply to a variant.
#
# The configuration data of a pool are listed in its directory object DbEcuConfigInfo. unknown_1 to unknown_3
# together name every configuration data object; unknown_4 is not used because it lacks the configuration data
# without records.
import os

from common_utils.enum_converters import get_db_file_type

CONFIG_INFO_OBJECT_ID = 'DbEcuConfigInfo'
CONFIG_INFO_LISTS = ('unknown_1', 'unknown_2', 'unknown_3')


# Get the PoolIDs of a project: the names of its .key files without the .key extension, sorted
### project_folder_path = project path (folder with .db and .key files)
def project_pool_ids(project_folder_path):
    return sorted(name[:-len('.key')] for name in os.listdir(project_folder_path) if name.endswith('.key'))


# Index of the configuration data of a project, built once in the constructor
### object_loader       = instance of ObjectLoader
### project_folder_path = project path (folder with .db and .key files)
### pool_ids            = PoolIDs to search; only ECU configuration pools with a DbEcuConfigInfo object count
# has_numeric_case_maps is True if a configuration data object has a number as map_key in its
# base_variant_to_case_map (database before version 0012); such objects are not part of the index
class ConfigDataIndex:
    def __init__(self, object_loader, project_folder_path, pool_ids):
        self.has_numeric_case_maps = False
        # configuration data objects in listing order
        self._entries = []
        for pool_id in pool_ids:
            if get_db_file_type(pool_id) != 'ECU Configuration':
                continue
            try:
                config_info = object_loader.load_object_by_id(project_folder_path, pool_id, CONFIG_INFO_OBJECT_ID)
            except KeyError:
                continue
            for object_id in _listed_object_ids(config_info):
                config_data = object_loader.load_object_by_id(project_folder_path, pool_id, object_id)
                case_map = config_data['base_variant_to_case_map']
                if any(isinstance(entry['map_key'], int) for entry in case_map):
                    self.has_numeric_case_maps = True
                    continue
                self._entries.append(config_data)

    # Get the configuration data objects that apply to a variant: first those valid for the whole base variant
    # (empty values), then those valid for the variant, each group sorted by short_name
    ### base_variant_name = name of the base variant
    ### variant_name      = name of the variant; equal to base_variant_name for the base variant itself
    def for_variant(self, base_variant_name, variant_name):
        base_level = []
        own = []
        for config_data in self._entries:
            levels = [entry['values'] for entry in config_data['base_variant_to_case_map']
                      if entry['map_key'] == base_variant_name]
            if any(not values for values in levels):
                base_level.append(config_data)
            elif variant_name != base_variant_name and any(variant_name in values for values in levels):
                own.append(config_data)
        return sorted(base_level, key=_short_name) + sorted(own, key=_short_name)


def _short_name(config_data):
    return config_data['short_name']


# Object ids named in unknown_1 to unknown_3 of DbEcuConfigInfo, without duplicates, in order of first occurrence
def _listed_object_ids(config_info):
    object_ids = {}
    for list_name in CONFIG_INFO_LISTS:
        for group in config_info[list_name]:
            for item in group['items']:
                object_ids.setdefault(item['object_id'])
    return list(object_ids)
