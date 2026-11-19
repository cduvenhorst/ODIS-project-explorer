# Helpers for the layer hierarchy of a project: the parent layer chain, the UDS check per base variant
# and the inheritance of services and DTC DOPs.
#
# The inheritance rule follows ODX: a layer inherits what its parent layers offer (PARENT-REF), minus the
# names listed in the NOT-INHERITED-... elements of that parent reference. What a layer defines itself comes first.
import functools
import os

# protocol_type values of UDS protocol layers start with one of these
UDS_PROTOCOL_TYPE_PREFIXES = ('ISO_15765_3', 'ISO_14229')

# VW projects carry the UDS and OBD protocol layers under fixed PoolIDs
VW_UDS_PROTOCOL_POOL = '0.0.0@PR_UDSOnCAN.pr'
VW_OBD_PROTOCOL_POOL = '0.0.0@PR_OBDOnCAN.pr'

LAYER_DATA_OBJECT_ID = '#RtGen_DB_LAYER_DATA'


# Load the layer data of a pool; the result is cached and must not be modified by the caller
### object_loader       = instance of ObjectLoader
### project_folder_path = project path (folder with .db and .key files)
### pool_id             = PoolID (file name) of the layer
@functools.lru_cache(maxsize=256)
def load_layer_data(object_loader, project_folder_path, pool_id):
    return object_loader.load_object_by_id(project_folder_path, pool_id, LAYER_DATA_OBJECT_ID)


# Load the layer data of a parent pool, or None if the pool or its layer data does not exist
def _load_parent_layer_data(object_loader, project_folder_path, pool_id):
    try:
        return load_layer_data(object_loader, project_folder_path, pool_id)
    except (FileNotFoundError, KeyError):
        return None


# Get all parent layers of a layer, nearest first (breadth first), without the layer itself and each pool once
### returns a list of (PoolID, layer data); parents that cannot be loaded are skipped,
### but the layer data of the layer itself must exist (the loader's error is raised otherwise)
def get_parent_layer_chain(object_loader, project_folder_path, pool_id):
    chain = []
    seen = {pool_id}
    queue = [(pool_id, load_layer_data(object_loader, project_folder_path, pool_id))]
    while queue:
        _, current = queue.pop(0)
        if current is None:
            continue
        for parent_pool_id in current['parent_layers']:
            if parent_pool_id in seen:
                continue
            seen.add(parent_pool_id)
            parent = _load_parent_layer_data(object_loader, project_folder_path, parent_pool_id)
            if parent is None:
                continue
            chain.append((parent_pool_id, parent))
            queue.append((parent_pool_id, parent))
    return chain


# Check whether a protocol type denotes UDS
### protocol_type = protocol_type of a layer data object, may be None
def is_uds_protocol_type(protocol_type):
    return bool(protocol_type) and protocol_type.startswith(UDS_PROTOCOL_TYPE_PREFIXES)


# Check whether the project has the fixed VW UDS protocol pool
def has_vw_uds_protocol(project_folder_path):
    return os.path.isfile(os.path.join(project_folder_path, VW_UDS_PROTOCOL_POOL + '.key'))


# Check whether a base variant speaks UDS: every base variant of a VW project, otherwise by the protocol types in its chain
def is_uds_base_variant(object_loader, project_folder_path, base_variant_pool_id):
    if has_vw_uds_protocol(project_folder_path):
        return True
    chain = get_parent_layer_chain(object_loader, project_folder_path, base_variant_pool_id)
    return any(is_uds_protocol_type(layer_data['protocol_type']) for _, layer_data in chain)


# Get the layer data objects needed for resolving DOP references of a UDS base variant, in order of relevance
### returns None if the base variant is not UDS
def get_protocol_layer_data_list(object_loader, project_folder_path, base_variant_pool_id):
    if not is_uds_base_variant(object_loader, project_folder_path, base_variant_pool_id):
        return None
    head = []
    head_pool_ids = set()
    if has_vw_uds_protocol(project_folder_path):
        # The upstream order: the parents of PR_UDSOnCAN, PR_UDSOnCAN itself, then PR_OBDOnCAN if the project has it
        uds_layer_data = load_layer_data(object_loader, project_folder_path, VW_UDS_PROTOCOL_POOL)
        pool_ids = list(uds_layer_data['parent_layers']) + [VW_UDS_PROTOCOL_POOL]
        if os.path.isfile(os.path.join(project_folder_path, VW_OBD_PROTOCOL_POOL + '.key')):
            pool_ids.append(VW_OBD_PROTOCOL_POOL)
        for pool_id in pool_ids:
            head.append(load_layer_data(object_loader, project_folder_path, pool_id))
            head_pool_ids.add(pool_id)
    rest = [layer_data for pool_id, layer_data in
            get_parent_layer_chain(object_loader, project_folder_path, base_variant_pool_id)
            if pool_id not in head_pool_ids]
    return head + rest


# Collect what a layer offers: its own entries first, then what each parent layer offers in turn, in the order of
# parent_layers; what a parent offers already includes what it inherits itself. A name that is already present is
# skipped, so with several parents the first parent in that order supplies a name that more than one of them offers.
### own_field / blocked_field = names of the layer data fields with the own entries and the NOT-INHERITED map
### key = function that gives the name of an entry
def _collect_inherited(object_loader, project_folder_path, layer_data, own_field, blocked_field, key, path):
    result = list(layer_data[own_field])
    blocked = {item['map_key']: set(item['strings']) for item in layer_data[blocked_field]}
    for parent_pool_id in layer_data['parent_layers']:
        if parent_pool_id in path:
            continue
        parent = _load_parent_layer_data(object_loader, project_folder_path, parent_pool_id)
        if parent is None:
            continue
        inherited = _collect_inherited(object_loader, project_folder_path, parent, own_field, blocked_field,
                                       key, path | {parent_pool_id})
        hidden = blocked.get(parent_pool_id, ())
        result.extend(entry for entry in inherited if key(entry) not in hidden)
    unique = []
    names = set()
    for entry in result:
        if key(entry) not in names:
            names.add(key(entry))
            unique.append(entry)
    return unique


# Get the diag-com primitive references of a layer including the inherited ones; for the order see _collect_inherited
### layer_data = layer data object of the layer (its own PoolID is not needed)
### returns entries shaped like layer_data['diag_com_primitive_references']
def get_inherited_diag_com_primitive_references(object_loader, project_folder_path, layer_data):
    return _collect_inherited(object_loader, project_folder_path, layer_data,
                              'diag_com_primitive_references', 'not_inherited_diag_com_primitives',
                              lambda entry: entry['map_key'], frozenset())


# Get the DTC DOP names of a layer including the inherited ones, without the ones hidden by not_inherited_dops
def get_inherited_dtc_dop_names(object_loader, project_folder_path, layer_data):
    return _collect_inherited(object_loader, project_folder_path, layer_data,
                              'dtc_dop_names', 'not_inherited_dops', lambda name: name, frozenset())
