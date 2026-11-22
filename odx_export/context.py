"""Per-pool state of the ODX export: loaded objects, usage tracking and counters."""
from collections import Counter

from odx_export.naming import layer_name, split_key

# Object types that never get a place in the ODX document.
_NOT_COUNTED_TYPES = ('DB_PROJECT_DATA', 'DB_KEY_VECTOR')


class PoolContext:
    def __init__(self, pool_id, objects, types, object_type=None, key_name=None):
        self.pool_id = pool_id
        self.layer = layer_name(pool_id)
        self.objects = objects  # key -> loaded object, in pool order
        self.types = types  # key -> type name
        self.object_type = object_type  # (pool_id, object_key) -> type name or None, other pools
        self.key_name = key_name  # hash -> key name or None
        self.written_caption_ids = set()  # SDG-CAPTION IDs already written in this document
        self.used = set()
        self.report = Counter()
        self.without_place = []
        self._length_key_owners = None  # parameter object ID -> owner ID, computed on first use
        self._without_place_seen = set()

    def take(self, key):
        """Return the object and remember it as used."""
        self.used.add(key)
        return self.objects[key]

    def keys(self, prefix, object_type=None):
        """Own keys '<prefix><layer>_...' in pool order, optionally of one type only."""
        head = prefix + self.layer + '_'
        return [key for key in self.objects
                if key.startswith(head) and (object_type is None or self.types[key] == object_type)]

    def own_id(self, key):
        """ID part of a key of this pool."""
        parts = split_key(key, self.layer)
        if parts is None:
            raise ValueError('key %r does not follow the naming rule of layer %r' % (key, self.layer))
        return parts[1]

    def target_type(self, reference):
        """Type of the referenced object, or None if it is unknown."""
        pool_id, object_id = reference.get('pool_id'), reference.get('object_id')
        if pool_id is None or not object_id:
            return None
        if pool_id == self.pool_id:
            return self.types.get(object_id)
        if self.object_type is None:
            return None
        return self.object_type(pool_id, object_id)

    def ordered(self, references, keys):
        """Keys in the order of a layer's reference list, then the remaining keys in pool order.

        Entries of the list are either {'reference': ...} or a reference itself.
        """
        wanted = set(keys)
        result = []
        seen = set()
        for entry in references or []:
            reference = entry.get('reference', entry) if isinstance(entry, dict) else None
            if not reference or reference.get('pool_id') != self.pool_id:
                continue
            object_id = reference.get('object_id')
            if object_id in wanted and object_id not in seen:
                seen.add(object_id)
                result.append(object_id)
        result.extend(key for key in keys if key not in seen)
        return result

    def mark_without_place(self, key):
        if key not in self._without_place_seen:
            self._without_place_seen.add(key)
            self.without_place.append(key)
        self.used.add(key)

    def unused(self):
        """Counter of the type names of the objects nobody took."""
        skipped = set(self.without_place)
        return Counter(type_name for key, type_name in self.types.items()
                       if key not in self.used and key not in skipped
                       and type_name not in _NOT_COUNTED_TYPES)
