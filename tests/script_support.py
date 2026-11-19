"""Test fixtures for the dump scripts: an in-memory object loader and layer data objects.

Everything here is invented data.
"""


class FakeObjectLoader:
    """In-memory stand-in for ObjectLoader, keyed by (pool_id, object_id).

    Counts the calls of load_object_by_id in `load_calls`. Hashable by identity,
    so it can serve as a cache key.
    """

    def __init__(self, objects):
        self.objects = objects
        self.load_calls = 0

    def load_object_by_id(self, input_folder_path, pool_id, object_id):
        self.load_calls += 1
        if not any(pool == pool_id for pool, _ in self.objects):
            raise FileNotFoundError(pool_id + '.key')
        return self.objects[(pool_id, object_id)]

    def load_object_by_reference(self, input_folder_path, reference):
        return self.load_object_by_id(input_folder_path, reference['pool_id'], reference['object_id'])

    def load_DOP_by_reference_without_PoolID(self, input_folder_path, layer_data_objects, reference):
        if reference['pool_id'] is not None:
            return self.load_object_by_reference(input_folder_path, reference)
        for layer_data_object in layer_data_objects:
            for item in layer_data_object['dop_references']:
                if item['map_key'] == reference['object_id']:
                    return self.load_object_by_reference(input_folder_path, item['reference'])
        raise RuntimeError('Could not find DOP reference: {}'.format(reference['object_id']))


def layer(**fields):
    """Layer data object with every field the scripts read, empty unless given."""
    result = {'parent_layers': [], 'protocol_type': None,
              'diag_com_primitive_references': [], 'not_inherited_diag_com_primitives': [],
              'dtc_dop_names': [], 'not_inherited_dops': [], 'dop_references': [],
              'location_type': None}
    result.update(fields)
    return result


def vector_map(mapping):
    """Build a string vector map (as read from a layer) from {key: [strings]}."""
    return [{'map_key': key, 'strings': list(strings)} for key, strings in mapping.items()]
