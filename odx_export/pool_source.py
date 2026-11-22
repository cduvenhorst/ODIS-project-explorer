"""The only file access of the ODX export: shared data pools of a project, loaded strictly."""
import os
import struct
import zlib

from classes.ObjectLoader import ObjectLoader
from classes.PblRecordManager import PblRecordManager
from common_utils import enum_converters
from common_utils.reference_resolver import ReferenceResolver
from object_loaders import __all__ as supported_object_types
from odx_export.context import PoolContext

SHARED_DATA_EXTENSION = '.sd'


class ProjectPools:
    def __init__(self, project_folder_path, string_storage, pbl_record_manager):
        self.__project_folder_path = project_folder_path
        self.__string_storage = string_storage
        self.__pbl_record_manager = pbl_record_manager
        # Per pool: object name -> type name, None for a pool without key or data file
        self.__type_maps = {}

    def __has_pool(self, pool_id):
        base = os.path.join(self.__project_folder_path, pool_id)
        return os.path.isfile(base + '.key') and os.path.isfile(base + '.db')

    def shared_data_pools(self):
        """Pools with key and data file whose name ends in '.sd', sorted."""
        pools = set()
        for filename in os.listdir(self.__project_folder_path):
            pool_id, extension = os.path.splitext(filename)
            if extension == '.db' and pool_id.endswith(SHARED_DATA_EXTENSION) and self.__has_pool(pool_id):
                pools.add(pool_id)
        return sorted(pools)

    def __object_name(self, key):
        # Same naming as dumpProject: a name key is the name, a hash is looked up, else 'hash <n>'
        if isinstance(key, str):
            return key
        name = self.__string_storage.get_ascii_string(key)
        return name if name is not None else 'hash {}'.format(key)

    def context(self, pool_id):
        """PoolContext with every object of the pool, loaded strictly and with resolved references."""
        object_loader = ObjectLoader(None, self.__string_storage, strict=True)
        # A resolver per pool, so that its caches go away with the pool
        resolver = ReferenceResolver(self.__project_folder_path, self.__string_storage, self.__pbl_record_manager)
        records = self.__pbl_record_manager.get_all_records(self.__project_folder_path, pool_id)
        objects = {}
        types = {}
        with open(os.path.join(self.__project_folder_path, pool_id + '.db'), 'rb') as db_file:
            for key, pbl_data in records.items():
                name = self.__object_name(key)
                # kernel: the hash is looked up first, then the name; the hash record wins
                if name in types and isinstance(key, str):
                    continue
                parts = ObjectLoader.get_object_parts_from_opened_db_file(pbl_data, db_file)
                type_name = enum_converters.get_object_type_enum(struct.unpack('<H', parts[0][:2])[0])
                types[name] = type_name
                # An object of a type without loader stays out of the objects and is reported as unused
                if type_name in supported_object_types:
                    obj = object_loader.load_object_by_parts(parts)
                    resolver.resolve_object(obj, pool_id)
                    objects[name] = obj
        self.__type_maps[pool_id] = dict(types)
        return PoolContext(pool_id, objects, types, object_type=self.object_type, key_name=self.key_name)

    def __read_type_map(self, pool_id):
        if not self.__has_pool(pool_id):
            return None
        records = self.__pbl_record_manager.get_all_records(self.__project_folder_path, pool_id)
        types = {}
        with open(os.path.join(self.__project_folder_path, pool_id + '.db'), 'rb') as db_file:
            for key, pbl_data in records.items():
                name = self.__object_name(key)
                if name in types and isinstance(key, str):
                    continue
                # Only the first two bytes of the first part are needed: the object type
                (file_position, parts) = PblRecordManager.parse_pbl_parts(pbl_data)
                db_file.seek(file_position)
                try:
                    head = zlib.decompressobj().decompress(db_file.read(parts[0][0]), 2)
                except zlib.error:
                    # A broken object of another pool is an unknown target, not an error of this pool
                    continue
                if len(head) < 2:
                    continue
                type_name = enum_converters.object_types.get(struct.unpack('<H', head)[0])
                if type_name is not None:
                    types[name] = type_name
        return types

    def object_type(self, pool_id, object_key):
        """Type name of an object of any pool, or None if the pool or the object is missing."""
        if pool_id not in self.__type_maps:
            self.__type_maps[pool_id] = self.__read_type_map(pool_id)
        types = self.__type_maps[pool_id]
        return types.get(object_key) if types is not None else None

    def key_name(self, key_hash):
        """Name of an object key hash, or None if the strings database does not have it."""
        return self.__string_storage.get_ascii_string(key_hash)
