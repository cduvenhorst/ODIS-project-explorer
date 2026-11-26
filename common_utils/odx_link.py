# Resolution of DB_ODX_LINK objects: an ODX link names a DOP by the layer document (DLC_<layer>) and the ID of the DOP
# inside it, and is resolved here through the DOP map (dop_references) of that layer.
from common_utils.enum_converters import get_db_file_type
from common_utils.layer_chain import load_layer_data

LAYER_DOCUMENT_PREFIX = 'DLC_'
DOP_PREFIX = 'DOP_'
ECU_CONFIGURATION_FILE_TYPE = 'ECU Configuration'

NOT_A_LAYER_DOCUMENT = 'ODX link document is not a layer: {}'
LAYER_NOT_FOUND = 'ODX link layer not found: {}'
LAYER_AMBIGUOUS = 'ODX link layer in more than one pool: {}'
DOP_NOT_FOUND = 'ODX link DOP not found: {}'
DOP_AMBIGUOUS = 'ODX link DOP listed more than once: {}'
DOP_NOT_LOADED = 'ODX link DOP could not be loaded: {}'


class OdxLinkResolver:
    ### object_loader       = instance of ObjectLoader
    ### project_folder_path = project path (folder with .db and .key files)
    ### pool_ids            = PoolIDs of the project; ECU configuration pools are not searched for layers
    def __init__(self, object_loader, project_folder_path, pool_ids):
        self.object_loader = object_loader
        self.project_folder_path = project_folder_path
        self.pool_ids = pool_ids
        self._pools_by_layer_name = None
        self._dop_entries_by_layer_name = {}

    # Map each layer name to the pools whose layer data carries it; built on first use
    def _get_pools_by_layer_name(self):
        if self._pools_by_layer_name is None:
            self._pools_by_layer_name = {}
            for pool_id in self.pool_ids:
                # ECU configuration pools hold the links, not the linked layers
                if get_db_file_type(pool_id) == ECU_CONFIGURATION_FILE_TYPE:
                    continue
                try:
                    layer_data = load_layer_data(self.object_loader, self.project_folder_path, pool_id)
                except (FileNotFoundError, KeyError):
                    continue
                self._pools_by_layer_name.setdefault(layer_data['layer_name'], []).append((pool_id, layer_data))
        return self._pools_by_layer_name

    # Map each object ID of the DOP map of a layer to its entries; built on first use of the layer
    ### layer_name = name of the layer, found in exactly one pool
    ### layer_data = layer data of that pool
    def _get_dop_entries(self, layer_name, layer_data):
        if layer_name not in self._dop_entries_by_layer_name:
            entries_by_object_id = {}
            for entry in layer_data['dop_references']:
                if entry is None:
                    continue
                entries_by_object_id.setdefault(entry['reference']['object_id'], []).append(entry)
            self._dop_entries_by_layer_name[layer_name] = entries_by_object_id
        return self._dop_entries_by_layer_name[layer_name]

    # Resolve a DB_ODX_LINK object to the DOP it names
    ### link = DB_ODX_LINK object with id_reference and document_reference
    ### returns (DOP object, None) or (None, note saying why the link could not be resolved)
    def resolve(self, link):
        document_reference = link['document_reference']
        if not document_reference.startswith(LAYER_DOCUMENT_PREFIX):
            return None, NOT_A_LAYER_DOCUMENT.format(document_reference)
        layer_name = document_reference[len(LAYER_DOCUMENT_PREFIX):]
        layers = self._get_pools_by_layer_name().get(layer_name, [])
        if not layers:
            return None, LAYER_NOT_FOUND.format(layer_name)
        if len(layers) > 1:
            return None, LAYER_AMBIGUOUS.format(layer_name)
        _, layer_data = layers[0]
        id_reference = link['id_reference'].removeprefix(DOP_PREFIX)
        dop_name = DOP_PREFIX + layer_name + '_' + id_reference
        entries = self._get_dop_entries(layer_name, layer_data).get(dop_name, [])
        if not entries:
            return None, DOP_NOT_FOUND.format(dop_name)
        if len(entries) > 1:
            return None, DOP_AMBIGUOUS.format(dop_name)
        try:
            dop = self.object_loader.load_object_by_reference(self.project_folder_path, entries[0]['reference'])
        except (FileNotFoundError, KeyError):
            return None, DOP_NOT_LOADED.format(dop_name)
        return dop, None
