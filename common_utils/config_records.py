# Helpers for the configuration data (MCD_DB_CONFIGURATION_DATA) of a project: listing them per pool
# and deciding which of them apply to a variant, and flat entries for their configuration records.
#
# The configuration data of a pool are listed in its directory object DbEcuConfigInfo. unknown_1 to unknown_3
# together name every configuration data object; unknown_4 is not used because it lacks the configuration data
# without records.
import os

from common_utils.coding_layout import NO_POSITION_NOTE, apply_dop
from common_utils.enum_converters import get_db_file_type
from common_utils.odx_link import OdxLinkResolver

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


# Sort key of a configuration data object
def _short_name(config_data):
    return config_data['short_name']


# The elements of a collection that are not None; the loaders keep empty elements, and a missing collection is empty
def _present(elements):
    return [element for element in elements or [] if element is not None]


# Object ids named in unknown_1 to unknown_3 of DbEcuConfigInfo, without duplicates, in order of first occurrence
def _listed_object_ids(config_info):
    object_ids = {}
    for list_name in CONFIG_INFO_LISTS:
        for group in config_info[list_name]:
            if group is None:
                continue
            for item in _present(group['items']):
                object_ids.setdefault(item['object_id'])
    return list(object_ids)


# Configuration data of a project as flat entries, for the configuration data that apply to a variant
### object_loader       = instance of ObjectLoader
### project_folder_path = project path (folder with .db and .key files)
### pool_ids            = PoolIDs to search; None means all PoolIDs of the project
class ConfigRecordSource:
    def __init__(self, object_loader, project_folder_path, pool_ids=None):
        if pool_ids is None:
            pool_ids = project_pool_ids(project_folder_path)
        self.object_loader = object_loader
        self.project_folder_path = project_folder_path
        self._index = ConfigDataIndex(object_loader, project_folder_path, pool_ids)
        self._resolver = OdxLinkResolver(object_loader, project_folder_path, pool_ids)
        # entries built per configuration data object, by id() of the object; the index keeps the objects alive
        self._entries_by_object = {}

    @property
    def has_numeric_case_maps(self):
        return self._index.has_numeric_case_maps

    # Get the flat entries of the configuration data that apply to a variant, in the order of ConfigDataIndex.for_variant
    ### base_variant_name = name of the base variant
    ### variant_name      = name of the variant; equal to base_variant_name for the base variant itself
    def entries_for_variant(self, base_variant_name, variant_name):
        entries = []
        for data in self._index.for_variant(base_variant_name, variant_name):
            # The configuration data valid for a whole base variant are built once, not once per variant.
            # The built entries are shared between the lists returned; callers only serialise them.
            if id(data) not in self._entries_by_object:
                self._entries_by_object[id(data)] = build_config_entries(
                    self.object_loader, self.project_folder_path, self._resolver, [data])[0]
            entries.append(self._entries_by_object[id(data)])
        return entries


# Build the flat entries of configuration data objects: one entry per object with its records, each with
# its services, connectors, data record names and one flat field per configuration item
### object_loader       = instance of ObjectLoader
### project_folder_path = project path (folder with .db and .key files)
### resolver            = OdxLinkResolver for the ODX links of the items
### config_data         = list of MCD_DB_CONFIGURATION_DATA objects
def build_config_entries(object_loader, project_folder_path, resolver, config_data):
    entries = []
    for data in config_data:
        records = []
        for record_reference in _present(data['configuration_record_references']):
            record = object_loader.load_object_by_reference(project_folder_path, record_reference['reference'])
            records.append(_build_record(object_loader, project_folder_path, resolver, record))
        entries.append({'short_name': data['short_name'], 'long_name': data['long_name'],
                        'long_name_id': data['long_name_id'], 'records': records})
    return entries


# Build the flat record of a configuration record object
def _build_record(object_loader, project_folder_path, resolver, record):
    items = []
    if record['configuration_id_item'] is not None:
        items.append(('configuration_id', record['configuration_id_item']))
    if record['data_id_item'] is not None:
        items.append(('data_id', record['data_id_item']))
    items.extend(('option', option_item) for option_item in _present(record['option_items']))
    items.extend(('system', system_item) for system_item in _present(record['system_items']))
    return {
        'short_name': record['short_name'],
        'long_name': record['long_name'],
        'long_name_id': record['long_name_id'],
        'byte_length': record['configuration_record_value_size'],
        'read_services': _link_ids(record['read_diag_com_primitives']),
        'write_services': _link_ids(record['write_diag_com_primitives']),
        'connectors': [_build_connector(connector) for connector in _present(record['diag_com_data_connectors'])],
        'fields': [_build_field(object_loader, project_folder_path, resolver, kind, item) for kind, item in items],
        'data_records': [reference['name'] for reference in _present(record['data_record_references'])],
    }


# IDs of the ODX links of a list, without empty elements
def _link_ids(links):
    return [link['id_reference'] for link in _present(links)]


# ID of an ODX link, None for a missing link
def _link_id(link):
    return link['id_reference'] if link is not None else None


# Build the flat connector of a diagnostic communication data connector
def _build_connector(connector):
    read_values = {entry['map_key']: entry['value'] for entry in _present(connector['read_parameter_value_map'])}
    write_values = {entry['map_key']: entry['value'] for entry in _present(connector['write_parameter_value_map'])}
    return {
        'read_service': _link_id(connector['read_diag_com_primitive']),
        'write_service': _link_id(connector['write_diag_com_primitive']),
        'size': connector['uncompressed_size'],
        'read_parameter_values': read_values,
        'write_parameter_values': write_values,
    }


# Build the flat field of a configuration item; every problem with its data type becomes the note of the field
### kind = item_kind of the field: configuration_id, data_id, option or system
def _build_field(object_loader, project_folder_path, resolver, kind, item):
    parameter = item['parameter']
    field = {
        'byte_position': None,
        'bit_position': None,
        'bit_length': None,
        'bit_mask': None,
        'long_name': item['long_name'],
        'long_name_id': item['long_name_id'],
        'parameter_type': None,
        'values': [],
        'default': item['physical_default_value'] if kind == 'option' else None,
        'note': None,
        'item_kind': kind,
        'item_values': [_build_item_value(value) for value in _present(item['item_values'])] if kind == 'option' else [],
        'system_parameter_name': item['system_parameter_name'] if kind == 'system' else None,
        '_standard_length': False,
    }
    if parameter is None:
        field['note'] = 'Item has no parameter'
    else:
        if parameter['is_byte_position_available']:
            field['byte_position'] = parameter['byte_position']
        field['bit_position'] = parameter['bit_position']
        parameter_type = parameter['mcd_parameter_type']
        if isinstance(parameter_type, str):
            parameter_type = parameter_type.removeprefix('e').replace('_', '-')
        field['parameter_type'] = parameter_type
        dop, note = _find_dop(object_loader, project_folder_path, resolver, parameter)
        field['note'] = note
        if dop is not None:
            _apply_parsed_dop(object_loader, project_folder_path, field, dop)
    if field['note'] is None and field['byte_position'] is None:
        field['note'] = NO_POSITION_NOTE
    del field['_standard_length']
    return field


# Build the flat value of an option item
def _build_item_value(value):
    return {'physical_value': value['physical_constant_value'], 'key': value['key'],
            'meaning': value['meaning'], 'meaning_id': value['meaning_id']}


# Find the DOP of a parameter: through its ODX link, else through its DOP reference
### returns (DOP object, None) or (None, note saying why there is none)
def _find_dop(object_loader, project_folder_path, resolver, parameter):
    dop_base = parameter['dop_base']
    if isinstance(dop_base, dict) and dop_base.get('#OBJECT_TYPE') == 'DB_ODX_LINK':
        return resolver.resolve(dop_base)
    reference = parameter['dop_base_reference']
    if reference is None:
        return None, 'Parameter has no DOP'
    if not reference['pool_id']:
        return None, 'DOP reference without pool: {}'.format(reference['object_id'])
    try:
        return object_loader.load_object_by_reference(project_folder_path, reference), None
    except (FileNotFoundError, KeyError):
        return None, 'DOP reference not found: {}/{}'.format(reference['pool_id'], reference['object_id'])


# Parse the DOP and write its layout into the field; a DOP that cannot be parsed becomes the note of the field
def _apply_parsed_dop(object_loader, project_folder_path, field, dop):
    # Imported here to avoid a circular import, as in common_utils/table_entries.py
    from dumpMWB import parse_dop
    try:
        parsed = parse_dop(object_loader, [], project_folder_path, dop)
    except (RuntimeError, KeyError) as error:
        field['note'] = 'DOP could not be parsed: {}'.format(error)
        return
    apply_dop(field, parsed)
