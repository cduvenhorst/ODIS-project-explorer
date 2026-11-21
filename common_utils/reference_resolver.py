"""Resolves references between objects of a project, to be shown beside the references."""
import os
import struct

from classes import DbObject
from classes.ObjectLoader import ObjectLoader
from common_utils import config_data, enum_converters
from common_utils.sdg_files import SdgFile

NOT_RESOLVABLE = 'not resolvable'


def insert_after(obj: dict, key: str, new_key: str, value) -> None:
    ### obj: dictionary changed in place
    ### key: existing key, new_key is placed directly behind it
    ### new_key: key to insert; an existing entry of that name is replaced and moved
    items = [(k, v) for (k, v) in obj.items() if k != new_key]
    obj.clear()
    for (k, v) in items:
        obj[k] = v
        if k == key:
            obj[new_key] = value
    if new_key not in obj:
        raise KeyError(key)


class ReferenceResolver:
    def __init__(self, project_folder_path, string_storage, pbl_record_manager):
        self.__project_folder_path = project_folder_path
        self.__string_storage = string_storage
        self.__pbl_record_manager = pbl_record_manager
        self.__object_loader = ObjectLoader(None, string_storage)
        
        # Per pool: PBL records (None if the pool has no key or data file) and SDG file (None if missing)
        self.__pbl_records = {}
        self.__sdg_files = {}
        
        # Short names (and row keys) per (pool, object)
        self.__short_names = {}
        self.__row_keys = {}
        
        # Short names of the configuration data objects seen, to find ConfigData folders nobody refers to
        self.configuration_data_short_names = set()
    
    
    # Walk an object (dictionaries and lists of any depth) and add the resolved references in place
    ### obj     = loaded object
    ### pool_id = Pool the object was loaded from, it resolves references with an empty pool_id
    def resolve_object(self, obj, pool_id):
        if isinstance(obj, list):
            for item in obj:
                self.resolve_object(item, pool_id)
            return
        if not isinstance(obj, dict):
            return
        
        # Resolve the contents first, the resolved groups are walked separately
        for value in list(obj.values()):
            self.resolve_object(value, pool_id)
        
        if obj.get('special_data_group_references'):
            groups = [self.__load_special_data_group(reference['object_id'], pool_id)
                      for reference in obj['special_data_group_references']]
            insert_after(obj, 'special_data_group_references', 'special_data_groups', groups)
        
        # The caption of every special data group, also of nested ones
        if obj.get('#OBJECT_TYPE') == 'MCD_DB_SPECIAL_DATA_GROUP' and 'caption_reference' in obj and 'caption' not in obj:
            insert_after(obj, 'caption_reference', 'caption', self.__load_caption(obj['caption_reference'], pool_id))
        
        object_type = obj.get('#OBJECT_TYPE')
        if object_type == 'MCD_DB_ECU_STATE_TRANSITION':
            for key in ('source_state', 'target_state'):
                if key in obj:
                    insert_after(obj, key, key + '_short_name', self.__short_name(obj[key], pool_id))
        elif object_type == 'MCD_DB_STATE_TRANSITION_ACTION':
            if obj.get('diag_com_primitive'):
                insert_after(obj, 'diag_com_primitive', 'diag_com_primitive_short_name',
                             self.__short_name(obj['diag_com_primitive'], pool_id))
        elif object_type == 'MCD_DB_ECU_STATE_CHART':
            if 'ecu_state_transitions' in obj:
                insert_after(obj, 'ecu_state_transitions', 'transitions', self.__chart_transitions(obj, pool_id))
        elif object_type == 'MCD_DB_TABLE_ROW_CONNECTOR':
            if obj.get('table_reference') and 'table_row' in obj:
                (table_short_name, row_key) = self.__table_row(obj['table_reference'], obj['table_row'], pool_id)
                insert_after(obj, 'table_row', 'table_short_name', table_short_name)
                insert_after(obj, 'table_short_name', 'table_row_key', row_key)
        elif object_type == 'MCD_DB_CONFIGURATION_DATA':
            if obj.get('short_name') is None:
                obj['configuration_data_files'] = NOT_RESOLVABLE
            else:
                self.configuration_data_short_names.add(obj['short_name'])
                obj['configuration_data_files'] = config_data.list_config_data_files(
                    self.__project_folder_path, config_data.CONFIG_DATA_PREFIX + obj['short_name'])
        elif object_type == 'MCD_DB_DATA_RECORD':
            obj['configuration_data_files'] = self.__data_record_files(obj)
    
    
    # Load an Object of a Pool
    ### pool_id         = Pool of the Object, an empty value stands for current_pool_id
    ### object_id       = str: name of the Object (hash is looked up first, then the name); int: hash of the name
    ### current_pool_id = Pool of the Object which holds the reference
    ### returns None if the Pool's files or the Object are missing
    def load_object(self, pool_id, object_id, current_pool_id):
        parts = self.__load_parts(pool_id, object_id, current_pool_id)
        if parts is None:
            return None
        return self.__object_loader.load_object_by_parts(parts)
    
    
    def __load_parts(self, pool_id, object_id, current_pool_id):
        if not pool_id:
            pool_id = current_pool_id
        records = self.__get_pbl_records(pool_id)
        if records is None:
            return None
        
        pbl_data = None
        if isinstance(object_id, int):
            pbl_data = records.get(object_id)
        else:
            # kernel: the hash is looked up first, then the name
            pbl_data = records.get(self.__string_storage.get_ascii_hash(object_id))
            if pbl_data is None:
                pbl_data = records.get(object_id)
        if pbl_data is None:
            return None
        
        return ObjectLoader.get_object_parts_from_db_file(pbl_data, self.__project_folder_path, pool_id)
    
    
    def __get_pbl_records(self, pool_id):
        if pool_id not in self.__pbl_records:
            base = os.path.join(self.__project_folder_path, pool_id)
            if os.path.isfile(base + '.key') and os.path.isfile(base + '.db'):
                self.__pbl_records[pool_id] = self.__pbl_record_manager.get_all_records(self.__project_folder_path, pool_id)
            else:
                self.__pbl_records[pool_id] = None
        return self.__pbl_records[pool_id]
    
    
    def __load_special_data_group(self, number, pool_id):
        if pool_id not in self.__sdg_files:
            self.__sdg_files[pool_id] = SdgFile.open(self.__project_folder_path, pool_id)
        sdg_file = self.__sdg_files[pool_id]
        if sdg_file is None:
            return NOT_RESOLVABLE
        record = sdg_file.record(number)
        if record is None:
            return NOT_RESOLVABLE
        
        # A record which cannot be decoded raises (strict), like any other loading error
        group = DbObject.load_object(record, self.__string_storage, strict=True)
        self.resolve_object(group, pool_id)
        return group
    
    
    def __load_caption(self, caption_reference, pool_id):
        if caption_reference is None:
            return None
        # The caption is looked up in the group's own Pool, the pool word of the reference is kept as read
        # (every caption in the surveyed data resolves there)
        parts = self.__load_parts(pool_id, caption_reference['object_key'], pool_id)
        if parts is None:
            return NOT_RESOLVABLE
        
        # Check the type before loading: an Object of a type without a loader must not raise
        object_type = enum_converters.object_types.get(struct.unpack('<H', parts[0][:2])[0])
        if object_type != 'MCD_DB_SPECIAL_DATA_GROUP_CAPTION':
            return NOT_RESOLVABLE
        return self.__object_loader.load_object_by_parts(parts)
    
    
    # Short name of the Object a reference points to, NOT_RESOLVABLE if it cannot be loaded
    ### reference       = dictionary with object_id and pool_id (an empty pool_id stands for current_pool_id)
    ### current_pool_id = Pool of the Object which holds the reference
    def __short_name(self, reference, current_pool_id):
        if not reference or not reference.get('object_id'):
            return NOT_RESOLVABLE
        key = (reference.get('pool_id') or current_pool_id, reference['object_id'])
        if key not in self.__short_names:
            loaded = self.load_object(key[0], key[1], current_pool_id)
            short_name = loaded.get('short_name') if isinstance(loaded, dict) else None
            self.__short_names[key] = short_name if short_name is not None else NOT_RESOLVABLE
        return self.__short_names[key]
    
    
    def __chart_transitions(self, chart, pool_id):
        services = self.__chart_services(chart, pool_id)
        transitions = []
        for entry in chart['ecu_state_transitions']:
            reference = entry['reference']
            transition = self.load_object(reference.get('pool_id'), reference['object_id'], pool_id)
            if not isinstance(transition, dict):
                transitions.append({'transition': NOT_RESOLVABLE, 'source_state': NOT_RESOLVABLE,
                                    'target_state': NOT_RESOLVABLE, 'services': []})
                continue
            # A reference with an empty pool_id is resolved in the Pool of the chart, which is where the transition was loaded from
            transition_pool_id = reference.get('pool_id') or pool_id
            name = transition.get('short_name')
            transitions.append({
                'transition': name if name is not None else NOT_RESOLVABLE,
                'source_state': self.__short_name(transition.get('source_state'), transition_pool_id),
                'target_state': self.__short_name(transition.get('target_state'), transition_pool_id),
                'services': services.get(name, [])})
        return transitions
    
    
    # Service short names per transition short name, from the DbStateChartData object of the chart's semantic
    def __chart_services(self, chart, pool_id):
        semantic = chart.get('semantic')
        if not semantic:
            return {}
        data = self.load_object(pool_id, 'DbStateChartData' + semantic, pool_id)
        if not isinstance(data, dict):
            return {}
        services = {}
        for entry in data.get('state_transition_transition_actions_map', []):
            services[entry['map_key']] = [
                self.__short_name(action.get('diag_com_primitive'), pool_id) if isinstance(action, dict) else NOT_RESOLVABLE
                for action in entry['items']]
        return services
    
    
    # Short name of the table and key of the row with the short name row_short_name, NOT_RESOLVABLE for what is not found
    def __table_row(self, table_reference, row_short_name, current_pool_id):
        table_pool_id = table_reference.get('pool_id') or current_pool_id
        table = self.load_object(table_pool_id, table_reference['object_id'], current_pool_id)
        if not isinstance(table, dict):
            return (NOT_RESOLVABLE, NOT_RESOLVABLE)
        table_short_name = table.get('short_name')
        if table_short_name is None:
            table_short_name = NOT_RESOLVABLE
        
        # A row reference with an empty pool_id is resolved in the Pool of the table
        for entry in table.get('table_key_map', []):
            row = self.__row(entry['reference'], table_pool_id)
            if row[0] == row_short_name:
                return (table_short_name, row[1])
        return (table_short_name, NOT_RESOLVABLE)
    
    
    # (short name, key) of a table row
    def __row(self, reference, table_pool_id):
        key = (reference.get('pool_id') or table_pool_id, reference['object_id'])
        if key not in self.__row_keys:
            row = self.load_object(key[0], key[1], table_pool_id)
            self.__row_keys[key] = (row.get('short_name'), row.get('key')) if isinstance(row, dict) else (None, None)
        return self.__row_keys[key]
    
    
    # Files of the ConfigData folder of the parent configuration data which match the coding data file name
    def __data_record_files(self, record):
        parent = record.get('parent_configuration_data_short_name')
        coding_data = record.get('coding_data')
        pattern = coding_data.get('file_name') if isinstance(coding_data, dict) else None
        if not parent or not pattern:
            return NOT_RESOLVABLE
        files = config_data.list_config_data_files(self.__project_folder_path, config_data.CONFIG_DATA_PREFIX + parent)
        return config_data.matching_config_data_files(files, pattern)
