"""The only file access of the ODX export: shared data and layer pools of a project, loaded strictly."""
import os
import struct
import zlib
from collections import Counter

from classes.ObjectLoader import ObjectLoader
from classes.PblRecordManager import PblRecordManager
from common_utils import enum_converters
from common_utils.reference_resolver import ReferenceResolver
from object_loaders import __all__ as supported_object_types
from odx_export.context import PoolContext
from odx_export.naming import layer_name

SHARED_DATA_EXTENSION = '.sd'
# Base variants with their variants, ECU variants, protocols, functional groups
LAYER_EXTENSIONS = ('.bv', '.ev', '.pr', '.fg')
_LAYER_TYPE = 'DB_LAYER_DATA'
_LAYER_FIELDS = ('layer_name', 'layer_id', 'location_type', 'parent_layers')


class ProjectPools:
    def __init__(self, project_folder_path, string_storage, pbl_record_manager):
        self.__project_folder_path = project_folder_path
        self.__string_storage = string_storage
        self.__pbl_record_manager = pbl_record_manager
        # Per pool: object name -> type name, None for a pool without key or data file
        self.__type_maps = {}
        self.__layers = {}  # per pool: layer descriptions, see layers()
        self.__foreign_layer_names = {}  # per other pool: its layer names for references into it

    def __has_pool(self, pool_id):
        base = os.path.join(self.__project_folder_path, pool_id)
        return os.path.isfile(base + '.key') and os.path.isfile(base + '.db')

    def __pools(self, extensions):
        pools = set()
        for filename in os.listdir(self.__project_folder_path):
            pool_id, extension = os.path.splitext(filename)
            if extension == '.db' and pool_id.endswith(extensions) and self.__has_pool(pool_id):
                pools.add(pool_id)
        return sorted(pools)

    def shared_data_pools(self):
        """Pools with key and data file whose name ends in '.sd', sorted."""
        return self.__pools(SHARED_DATA_EXTENSION)

    def layer_pools(self):
        """Pools with key and data file whose name ends in '.bv', '.ev', '.pr' or '.fg', sorted."""
        return self.__pools(LAYER_EXTENSIONS)

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
                    objects[name] = object_loader.load_object_by_parts(parts)
        self.__type_maps[pool_id] = dict(types)
        self.__layers[pool_id] = [_layer_description(key, objects[key])
                                  for key, type_name in types.items() if type_name == _LAYER_TYPE]
        unpooled = self.__resolve_variant_references(pool_id, objects, types)
        # After the pools are filled in, so that the shown names come from the pool that holds the object
        for obj in objects.values():
            resolver.resolve_object(obj, pool_id)
        pool_layers = [layer['layer_name'] for layer in self.__layers[pool_id]]
        # The survey found the pool's own layer name among its layers in every pool; a pool without it
        # keeps the naming rule of 4-C1 (layer name from the pool name) in addition.
        if layer_name(pool_id) not in pool_layers:
            pool_layers.append(layer_name(pool_id))
        ctx = PoolContext(pool_id, objects, types, object_type=self.object_type, key_name=self.key_name,
                          pool_layers=pool_layers, foreign_layers=self.__foreign_layers)
        ctx.report.update(unpooled)
        return ctx

    def __resolve_variant_references(self, pool_id, objects, types):
        """Fill in the pool of the references without one in a .ev pool; Counter of the informative counters.

        Many references of .ev pools carry no pool ID. Modelled on upstream's
        ObjectLoader.load_DOP_by_reference_without_PoolID (own variant, base variant, protocol); here by type
        map along the breadth-first parent chain (parent_layers from the pool's own layer, shared data parents
        included): such a reference points into the own pool if it holds the object, else into the first pool
        of the chain that does, each pool once.
        A name that no pool holds (a short name in a matching pattern, say) stays without pool. Other pools are
        unchanged."""
        if not pool_id.endswith('.ev'):
            return Counter()
        chain = self.__parent_chain(pool_id)

        def find_pool(object_id):
            if object_id in types:
                return pool_id
            return next((parent for parent in chain if self.object_type(parent, object_id) is not None), None)

        counts = Counter()
        for obj in objects.values():
            counts.update(resolve_unpooled_references(obj, find_pool))
        return Counter({
            'unpooled_references_resolved_to_parent': sum(count for target, count in counts.items()
                                                          if target not in (None, pool_id)),
            'unpooled_references_unresolved': counts[None]})

    def __parent_chain(self, pool_id):
        """Pools of the parent layers of a pool, breadth first, each once and without the pool itself."""
        chain = []
        seen = {pool_id}
        queue = [pool_id]
        while queue:
            try:
                layers = self.layers(queue.pop(0))
            except Exception:
                # A broken layer object of another pool ends the chain there, not this pool
                layers = []
            for layer in layers:
                for parent in layer['parent_layers'] or []:
                    if parent not in seen:
                        seen.add(parent)
                        chain.append(parent)
                        queue.append(parent)
        return chain

    def __foreign_layers(self, pool_id):
        if pool_id not in self.__foreign_layer_names:
            try:
                names = [layer['layer_name'] for layer in self.layers(pool_id)]
            except Exception:
                # A broken layer object of another pool leaves the naming rule of 4-C1, not an error of this pool
                names = []
            self.__foreign_layer_names[pool_id] = names or [layer_name(pool_id)]
        return self.__foreign_layer_names[pool_id]

    def layers(self, pool_id):
        """{'key', 'layer_name', 'layer_id', 'location_type', 'parent_layers'} per DB_LAYER_DATA of a pool.

        In pool order; only the layer objects are loaded. [] for a missing pool.
        """
        if pool_id not in self.__layers:
            self.__layers[pool_id] = self.__read_layers(pool_id)
        return self.__layers[pool_id]

    def __read_layers(self, pool_id):
        types = self.__type_map(pool_id)
        wanted = {name for name, type_name in (types or {}).items() if type_name == _LAYER_TYPE}
        if not wanted:
            return []
        object_loader = ObjectLoader(None, self.__string_storage, strict=True)
        records = self.__pbl_record_manager.get_all_records(self.__project_folder_path, pool_id)
        layers = {}
        with open(os.path.join(self.__project_folder_path, pool_id + '.db'), 'rb') as db_file:
            for key, pbl_data in records.items():
                name = self.__object_name(key)
                # Same rule as in context(): the hash record wins over the name record
                if name not in wanted or (name in layers and isinstance(key, str)):
                    continue
                parts = ObjectLoader.get_object_parts_from_opened_db_file(pbl_data, db_file)
                layers[name] = _layer_description(name, object_loader.load_object_by_parts(parts))
        return list(layers.values())

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

    def __type_map(self, pool_id):
        if pool_id not in self.__type_maps:
            self.__type_maps[pool_id] = self.__read_type_map(pool_id)
        return self.__type_maps[pool_id]

    def object_type(self, pool_id, object_key):
        """Type name of an object of any pool, or None if the pool or the object is missing."""
        types = self.__type_map(pool_id)
        return types.get(object_key) if types is not None else None

    def key_name(self, key_hash):
        """Name of an object key hash, or None if the strings database does not have it."""
        return self.__string_storage.get_ascii_string(key_hash)


def _layer_description(key, obj):
    description = {'key': key}
    description.update((field, obj[field]) for field in _LAYER_FIELDS)
    return description


def resolve_unpooled_references(obj, find_pool):
    """Fill in the pool of every reference without one, at any depth of dicts and lists, in place.

    find_pool(object_id) gives the pool that holds the object, or None; such a reference stays as it is.
    Returns a Counter: per pool the references resolved into it, under None the ones left unresolved."""
    counts = Counter()
    pending = [obj]
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
            continue
        if not isinstance(item, dict):
            continue
        if 'object_id' in item and 'pool_id' in item and item['pool_id'] is None and item['object_id']:
            pool_id = find_pool(item['object_id'])
            counts[pool_id] += 1
            if pool_id is not None:
                item['pool_id'] = pool_id
        pending.extend(item.values())
    return counts
