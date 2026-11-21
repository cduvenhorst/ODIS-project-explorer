"""Resolves references between objects of a project, to be shown beside the references."""
import os

from classes import DbObject
from classes.ObjectLoader import ObjectLoader
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
        if 'caption_reference' in obj and 'caption' not in obj:
            insert_after(obj, 'caption_reference', 'caption', self.__load_caption(obj['caption_reference'], pool_id))
    
    
    # Load an Object of a Pool
    ### pool_id         = Pool of the Object, an empty value stands for current_pool_id
    ### object_id       = str: name of the Object (hash is looked up first, then the name); int: hash of the name
    ### current_pool_id = Pool of the Object which holds the reference
    ### returns None if the Pool's files or the Object are missing
    def load_object(self, pool_id, object_id, current_pool_id):
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
        
        parts = ObjectLoader.get_object_parts_from_db_file(pbl_data, self.__project_folder_path, pool_id)
        return self.__object_loader.load_object_by_parts(parts)
    
    
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
        caption = self.load_object(caption_reference['pool_id'], caption_reference['object_key'], pool_id)
        if not isinstance(caption, dict) or caption.get('#OBJECT_TYPE') != 'MCD_DB_SPECIAL_DATA_GROUP_CAPTION':
            return NOT_RESOLVABLE
        return caption
