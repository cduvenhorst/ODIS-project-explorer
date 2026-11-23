"""Per-pool state of the ODX export: loaded objects, usage tracking and counters."""
import copy
from collections import Counter

from odx_export.naming import layer_name, split_key

# Object types that never get a place in the ODX document.
_NOT_COUNTED_TYPES = ('DB_PROJECT_DATA', 'DB_KEY_VECTOR')


class PoolContext:
    """State of one pool; for_layer() gives the view of one of its layers, which shares that state."""

    def __init__(self, pool_id, objects, types, object_type=None, key_name=None,
                 pool_layers=None, foreign_layers=None):
        self.pool_id = pool_id
        self.layer = layer_name(pool_id)  # the layer being written; for_layer() changes it
        self.pool_layers = list(pool_layers) if pool_layers is not None else [self.layer]
        self.objects = objects  # key -> loaded object, in pool order
        self.types = types  # key -> type name
        self.object_type = object_type  # (pool_id, object_key) -> type name or None, other pools
        self.key_name = key_name  # hash -> key name or None
        self.foreign_layers = foreign_layers  # pool_id -> layer names of another pool, or None
        self.written_caption_ids = set()  # SDG-CAPTION IDs already written in this layer
        self.used = set()
        self.report = Counter()
        self.without_place = []
        self._caches = {'length_key_owners': None, 'length_key_owner_layers': None}  # shared by all views
        self._without_place_seen = set()

    @property
    def _length_key_owners(self):
        """Parameter object ID -> owner ID, computed on first use."""
        return self._caches['length_key_owners']

    @_length_key_owners.setter
    def _length_key_owners(self, owners):
        self._caches['length_key_owners'] = owners

    def for_layer(self, layer):
        """View of one layer of the pool with its own caption IDs; everything else is shared."""
        view = copy.copy(self)
        view.layer = layer
        view.written_caption_ids = set()
        return view

    def naming_layer(self, object_key):
        """Longest layer name of the pool that the key follows, or None."""
        return _longest_match(object_key, self.pool_layers)

    def target_layer(self, pool_id, object_id):
        """Layer that holds a referenced object: the layer its key names, else the pool's layer name."""
        if pool_id == self.pool_id:
            layers = self.pool_layers
        elif self.foreign_layers is not None:
            layers = self.foreign_layers(pool_id)
        else:
            layers = ()
        return _longest_match(object_id, layers) or layer_name(pool_id)

    def take(self, key):
        """Return the object and remember it as used."""
        self.used.add(key)
        return self.objects[key]

    def owns(self, key):
        """Whether the key follows the naming rule of the layer being written."""
        if split_key(key, self.layer) is None:
            return False
        # A key of a layer whose name starts with this one ('V1' and 'V1_X') belongs to that layer.
        return len(self.pool_layers) == 1 or self.naming_layer(key) == self.layer

    def keys(self, prefix, object_type=None):
        """Own keys '<prefix><layer>_...' of this layer in pool order, optionally of one type only."""
        head = prefix + self.layer + '_'
        return [key for key in self.objects
                if key.startswith(head) and (object_type is None or self.types[key] == object_type)
                and self.owns(key)]

    def own_id(self, key):
        """ID part of a key of this pool, split with the layer the key names."""
        layer = self.naming_layer(key)
        parts = split_key(key, layer) if layer is not None else None
        if parts is None:
            raise ValueError('key %r does not follow the naming rule of a layer of %r' % (key, self.pool_id))
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
            if reference:
                reference = resolve_unpooled(self, reference)
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


def resolve_unpooled(ctx, reference):
    """Reference with the pool filled in where a .ev pool leaves it out.

    The layer lists of .ev pools carry no pool ID; a reference without one whose object lies in the pool
    belongs to the pool, any other is returned unchanged and reported. Other pools are left as they are."""
    if not ctx.pool_id.endswith('.ev') or reference.get('pool_id') is not None:
        return reference
    if reference.get('object_id') in ctx.objects:
        return dict(reference, pool_id=ctx.pool_id)
    ctx.report['unpooled_reference_not_in_pool'] += 1
    return reference


def _longest_match(object_key, layers):
    best = None
    for layer in layers:
        if (best is None or len(layer) > len(best)) and split_key(object_key, layer) is not None:
            best = layer
    return best
