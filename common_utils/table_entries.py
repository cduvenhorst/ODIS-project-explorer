# Reading of the table entries behind coding, measurement value (MWB) and adaptation services.
#
# A service is selected by its VW service name first; if the variant does not carry that name, by the layout of
# its request and response (UDS service ID and the byte positions of the table key and table structure).
import collections

from common_utils.layer_chain import get_inherited_diag_com_primitive_references

# Names of the Coding service, in order of preference: the VW name and the Porsche name
CODING_SERVICE_NAMES = ('DiagnServi_WriteDataByIdentVariaCodinTextu', 'CodingValue_Write')
VW_MWB_SERVICE_NAME = 'DiagnServi_ReadDataByIdentMeasuValue'
VW_ADAPTATION_SERVICE_NAME = 'DiagnServi_WriteDataByIdentCalibData'

KIND_CODING = 'coding'
KIND_MWB = 'mwb'
KIND_ADAPTATION = 'adaptation'

SERVICE_ID_READ_DATA_BY_IDENTIFIER = 0x22
SERVICE_ID_WRITE_DATA_BY_IDENTIFIER = 0x2E

# Families of tables, told apart by the DOP of the table key: the key is a text (name) or a plain number (decimal)
FAMILY_NAMES = 'names'
FAMILY_DECIMAL = 'decimal'

TABLE_KEY_TYPE = 'MCD_DB_PARAMETER_TABLE_KEY'
TABLE_STRUCT_TYPE = 'MCD_DB_PARAMETER_TABLESTRUCT'

# key_parameter / struct_parameter are the raw parameter objects of the request (coding, adaptation) or of the
# positive response (MWB); is_vw_table_service is true for the services selected by their VW name
SelectedService = collections.namedtuple('SelectedService',
                                         ['short_name', 'key_parameter', 'struct_parameter', 'is_vw_table_service'])


def _find_parameters(parameters):
    # upstream: the last parameter of each type counts
    key_parameter = None
    struct_parameter = None
    for parameter in parameters:
        if parameter['#OBJECT_TYPE'] == TABLE_KEY_TYPE:
            key_parameter = parameter
        if parameter['#OBJECT_TYPE'] == TABLE_STRUCT_TYPE:
            struct_parameter = parameter
    return key_parameter, struct_parameter


def _at_byte_edge(parameter, byte_position):
    return parameter.get('byte_position') == byte_position and parameter.get('bit_position') == 0


def _is_coded_service_id(parameter, service_id):
    if parameter.get('byte_position') != 0 or parameter.get('mcd_parameter_type') != 'eCODED_CONST':
        return False
    default_value = parameter.get('default_value')
    return isinstance(default_value, dict) and default_value.get('value') == service_id


class TableEntryReader:
    # One instance per base variant; it buffers the loaded services, requests and responses by (pool_id, object_id)
    def __init__(self, object_loader, project_folder_path):
        self.object_loader = object_loader
        self.project_folder_path = project_folder_path
        self._objects = {}
        # Per table (pool_id, object_id): row short name -> (map key, row reference)
        self._row_maps = {}

    def _load(self, reference):
        key = (reference['pool_id'], reference['object_id'])
        if key not in self._objects:
            self._objects[key] = self.object_loader.load_object_by_reference(self.project_folder_path, reference)
        return self._objects[key]

    def _load_service(self, diag_com_ref):
        # References to objects that are no services (jobs, for example) are skipped
        service = self._load(diag_com_ref['reference'])
        if service.get('#OBJECT_TYPE') != 'MCD_DB_SERVICE':
            return None
        return service

    # Select the services of a kind that an ECU variant offers (own and inherited), in the order of the inherited list
    ### kind = KIND_CODING, KIND_MWB or KIND_ADAPTATION
    ### returns a list of SelectedService, empty if nothing matches
    ### raises RuntimeError for a service selected by its VW name that does not have the expected layout
    def select_services(self, ecu_variant_layer_data, kind):
        diag_com_refs = get_inherited_diag_com_primitive_references(self.object_loader, self.project_folder_path,
                                                                    ecu_variant_layer_data)
        if kind == KIND_CODING:
            return self._select_coding(diag_com_refs)
        if kind == KIND_MWB:
            return self._select_by_name_or_structure(diag_com_refs, VW_MWB_SERVICE_NAME, self._mwb_by_name,
                                                     self._mwb_by_structure)
        if kind == KIND_ADAPTATION:
            return self._select_by_name_or_structure(diag_com_refs, VW_ADAPTATION_SERVICE_NAME,
                                                     self._adaptation_by_name, self._adaptation_by_structure)
        raise ValueError('Unknown kind of table entries: {}'.format(kind))

    @staticmethod
    def _find_by_name(diag_com_refs, name):
        for diag_com_ref in diag_com_refs:
            if diag_com_ref['map_key'] == name:
                return diag_com_ref
        return None

    def _select_by_name_or_structure(self, diag_com_refs, vw_name, by_name, by_structure):
        vw_ref = self._find_by_name(diag_com_refs, vw_name)
        if vw_ref is not None:
            return [by_name(vw_ref)]
        result = []
        for diag_com_ref in diag_com_refs:
            selected = by_structure(diag_com_ref)
            if selected is not None:
                result.append(selected)
        return result

    # coding: the first name of CODING_SERVICE_NAMES that the variant carries decides
    def _select_coding(self, diag_com_refs):
        for service_name in CODING_SERVICE_NAMES:
            diag_com_ref = self._find_by_name(diag_com_refs, service_name)
            if diag_com_ref is None:
                continue
            service = self._load(diag_com_ref['reference'])
            request = self._load(service['request_reference'])
            key_parameter, struct_parameter = _find_parameters(request['request_parameters'])
            if key_parameter is None:
                raise RuntimeError('Could not find table key request parameter')
            if struct_parameter is None:
                raise RuntimeError('Could not find table struct request parameter')
            # In a service 0x2E request, the DID is expected at BYTE-POSITION 1 and the Coding data at BYTE-POSITION 3 (both at byte edge)
            if not _at_byte_edge(key_parameter, 1):
                raise RuntimeError('Expected BYTE-POSITION 1 and BIT-POSITION 0 for Coding table key, not {} and {}'.format(key_parameter['byte_position'], key_parameter['bit_position']))
            if not _at_byte_edge(struct_parameter, 3):
                raise RuntimeError('Expected BYTE-POSITION 3 and BIT-POSITION 0 for Coding table struct, not {} and {}'.format(struct_parameter['byte_position'], struct_parameter['bit_position']))
            return [SelectedService(service_name, key_parameter, struct_parameter,
                                    service_name == CODING_SERVICE_NAMES[0])]
        return []

    # mwb by VW name: the checks and messages of the upstream dumpMWB
    def _mwb_by_name(self, diag_com_ref):
        service = self._load(diag_com_ref['reference'])
        # The service should only have one positve response referenced
        if len(service['positive_response_references']) != 1:
            raise RuntimeError('RDBI service has multiple positive responses')
        response = self._load(service['positive_response_references'][0]['reference'])
        key_parameter, struct_parameter = _find_parameters(response['response_parameters'])
        if key_parameter is None:
            raise RuntimeError('Could not find table key response parameter')
        if struct_parameter is None:
            raise RuntimeError('Could not find table struct response parameter')
        # In a service 0x22 response, the DID is expected at BYTE-POSITION 1 and the MWB at BYTE-POSITION 3 (both at byte edge)
        if not _at_byte_edge(key_parameter, 1):
            raise RuntimeError('Expected BYTE-POSITION 1 and BIT-POSITION 0 for MWB table key, not {} and {}'.format(key_parameter['byte_position'], key_parameter['bit_position']))
        if not _at_byte_edge(struct_parameter, 3):
            raise RuntimeError('Expected BYTE-POSITION 3 and BIT-POSITION 0 for MWB table struct, not {} and {}'.format(struct_parameter['byte_position'], struct_parameter['bit_position']))
        return SelectedService(diag_com_ref['map_key'], key_parameter, struct_parameter, True)

    # mwb by layout: request 0x22 at byte 0, exactly one positive response with exactly one key at byte 1 and
    # exactly one structure at byte 3; anything else is skipped
    def _mwb_by_structure(self, diag_com_ref):
        service = self._load_service(diag_com_ref)
        if service is None:
            return None
        request = self._load(service['request_reference'])
        if not any(_is_coded_service_id(parameter, SERVICE_ID_READ_DATA_BY_IDENTIFIER)
                   for parameter in request['request_parameters']):
            return None
        if len(service['positive_response_references']) != 1:
            return None
        response = self._load(service['positive_response_references'][0]['reference'])
        return self._unique_key_and_struct(diag_com_ref['map_key'], response['response_parameters'])

    # adaptation by VW name: the checks and messages of the upstream dumpAdaptations
    def _adaptation_by_name(self, diag_com_ref):
        service = self._load(diag_com_ref['reference'])
        request = self._load(service['request_reference'])
        key_parameter, struct_parameter = _find_parameters(request['request_parameters'])
        if key_parameter is None:
            raise RuntimeError('Could not find table key request parameter')
        if struct_parameter is None:
            raise RuntimeError('Could not find table struct request parameter')
        # In a service 0x2E request, the DID is expected at BYTE-POSITION 1 and the Adaptation data at BYTE-POSITION 3 (both at byte edge)
        if not _at_byte_edge(key_parameter, 1):
            raise RuntimeError('Expected BYTE-POSITION 1 and BIT-POSITION 0 for Adaptation table key, not {} and {}'.format(key_parameter['byte_position'], key_parameter['bit_position']))
        #if struct_parameter['byte_position'] != 3 or struct_parameter['bit_position'] != 0:
        #    raise RuntimeError('Expected BYTE-POSITION 3 and BIT-POSITION 0 for Adaptation table struct, not {} and {}'.format(struct_parameter['byte_position'], struct_parameter['bit_position']))
        return SelectedService(diag_com_ref['map_key'], key_parameter, struct_parameter, True)

    # adaptation by layout: every service except the coding services whose request has 0x2E at byte 0, exactly one
    # key at byte 1 and exactly one structure at byte 3
    def _adaptation_by_structure(self, diag_com_ref):
        if diag_com_ref['map_key'] in CODING_SERVICE_NAMES:
            return None
        service = self._load_service(diag_com_ref)
        if service is None:
            return None
        request = self._load(service['request_reference'])
        parameters = request['request_parameters']
        if not any(_is_coded_service_id(parameter, SERVICE_ID_WRITE_DATA_BY_IDENTIFIER) for parameter in parameters):
            return None
        return self._unique_key_and_struct(diag_com_ref['map_key'], parameters)

    @staticmethod
    def _unique_key_and_struct(short_name, parameters):
        keys = [p for p in parameters if p['#OBJECT_TYPE'] == TABLE_KEY_TYPE]
        structs = [p for p in parameters if p['#OBJECT_TYPE'] == TABLE_STRUCT_TYPE]
        if len(keys) != 1 or len(structs) != 1:
            return None
        if not _at_byte_edge(keys[0], 1) or not _at_byte_edge(structs[0], 3):
            return None
        return SelectedService(short_name, keys[0], structs[0], False)

    # Read the table entries of the selected services
    ### layer_data_objects = the layer data used to resolve DOP references without PoolID (ECU variant first)
    ### services = list of SelectedService, as returned by select_services
    ### returns a list of entries with did, long_name, long_name_id, description, byte_position, bit_position and
    ### structure; entries that no VW table service delivers also carry services (sorted short names)
    ### Entries of VW table services come first, in their order; all others are sorted by (did, services[0])
    def get_entries(self, layer_data_objects, services):
        # dumpMWB imports this module, so parse_dop is imported here to avoid a circular import. When dumpMWB.py runs
        # as a script, this loads it a second time; its top level only defines functions and loads the PBL library
        # again (the argument parser sits under __main__), so that is harmless.
        from dumpMWB import parse_dop

        # Parsed objects depend on layer_data_objects, so they are only buffered within this call
        call = _EntryCall(self, parse_dop, layer_data_objects)

        entries = {}
        service_names = {}
        vw_identities = set()
        for service in services:
            for identity, entry in call.service_entries(service):
                if identity not in entries:
                    entries[identity] = entry
                    service_names[identity] = set()
                service_names[identity].add(service.short_name)
                if service.is_vw_table_service:
                    vw_identities.add(identity)

        vw_entries = []
        other_entries = []
        for identity, entry in entries.items():
            if identity in vw_identities:
                vw_entries.append(entry)
            else:
                entry['services'] = sorted(service_names[identity])
                other_entries.append(entry)
        other_entries.sort(key=lambda entry: (entry['did'], entry['services'][0]))
        return vw_entries + other_entries

    # Read the coding entries of an ECU variant together with the rows of its coding table that other services
    # address: the measurement value and adaptation services that are no VW table services and reference one row of
    # the same table as the coding service
    ### returns None if the variant has no coding service; a VW coding service or one without row reference reads
    ### its whole table and nothing else
    def get_related_coding_entries(self, layer_data_objects, ecu_variant_layer_data):
        coding_services = self.select_services(ecu_variant_layer_data, KIND_CODING)
        if not coding_services:
            return None
        coding_service = coding_services[0]
        if coding_service.is_vw_table_service or not coding_service.key_parameter['is_table_row_reference']:
            return self.get_entries(layer_data_objects, coding_services)
        coding_table_key = _table_key(coding_service.key_parameter['table_reference'])
        related_services = []
        for kind in (KIND_MWB, KIND_ADAPTATION):
            for service in self.select_services(ecu_variant_layer_data, kind):
                if (not service.is_vw_table_service and service.key_parameter['is_table_row_reference']
                        and _table_key(service.key_parameter['table_reference']) == coding_table_key):
                    related_services.append(service)
        return self.get_entries(layer_data_objects, coding_services + related_services)

    def _row_map(self, table_key, table):
        if table_key not in self._row_maps:
            self._row_maps[table_key] = {self._load(item['reference'])['short_name']: (item['map_key'], item['reference'])
                                         for item in table['table_key_map']}
        return self._row_maps[table_key]


def _table_key(reference):
    return (reference['pool_id'], reference['object_id'])


def _entry(did, long_name, long_name_id, row):
    # The checks of the upstream scripts, except that a default value of the row no longer aborts
    if row['parameter_type'] != 'VALUE':
        raise RuntimeError('Wrong parameter type for table row parameter: {}'.format(row['parameter_type']))
    structure = row['dop']
    # A row whose DOP could not be found carries the error marker of parse_dop as its structure
    if '#error' not in structure and structure['type'] != 'STRUCTURE':
        raise RuntimeError('Wrong data type for parameter structure: {}'.format(structure['type']))
    return {
        'did': did,
        'long_name': long_name,
        'long_name_id': long_name_id,
        'description': row['description'],
        'byte_position': row['byte_position'],
        'bit_position': row['bit_position'],
        'structure': structure
    }


class _EntryCall:
    # State of one get_entries call: the parsed rows, table key families and table keys
    def __init__(self, reader, parse_dop, layer_data_objects):
        self.reader = reader
        self.parse_dop = parse_dop
        self.layer_data_objects = layer_data_objects
        self._parsed_rows = {}
        self._families = {}
        self._parsed_keys = {}

    def _parse(self, obj):
        return self.parse_dop(self.reader.object_loader, self.layer_data_objects, self.reader.project_folder_path, obj)

    def _row(self, reference):
        key = _table_key(reference)
        if key not in self._parsed_rows:
            self._parsed_rows[key] = self._parse(self.reader._load(reference))
        return self._parsed_rows[key]

    def _family(self, table_key, table):
        if table_key not in self._families:
            key_dop = self._parse(self.reader._load(table['dop_simple_reference']))
            category = key_dop.get('compu_category')
            coded = key_dop.get('coded_base_data_type')
            physical = key_dop.get('physical_base_data_type')
            if (category, coded, physical) == ('TEXTTABLE', 'A_UINT32', 'A_UNICODE2STRING'):
                self._families[table_key] = FAMILY_NAMES
            elif (category, coded, physical) == ('IDENTICAL', 'A_UINT32', 'A_UINT32'):
                self._families[table_key] = FAMILY_DECIMAL
            else:
                raise RuntimeError('Unexpected table key DOP: {} {} -> {}'.format(category, coded, physical))
        return self._families[table_key]

    def _keys(self, table_key, key_parameter):
        if table_key not in self._parsed_keys:
            self._parsed_keys[table_key] = self._parse(key_parameter)['keys']
        return self._parsed_keys[table_key]

    # Yields (identity, entry) for each entry of a service; the identity of a row is (pool_id, object_id of the
    # table, map key), extended by the DID because the VW whole table can give one row under two DIDs
    def service_entries(self, service):
        table_reference = service.key_parameter['table_reference']
        table_key = _table_key(table_reference)
        table = self.reader._load(table_reference)
        family = self._family(table_key, table)
        if service.is_vw_table_service or not service.key_parameter['is_table_row_reference']:
            if family == FAMILY_NAMES:
                return self._whole_name_table(table_key, service)
            return self._whole_decimal_table(table_key, table)
        return [self._referenced_row(table_key, table, family, service)]

    # The upstream way: the keys resolve DIDs to names, the rows are found by name
    def _whole_name_table(self, table_key, service):
        parsed_keys = self._parse(service.key_parameter)
        parsed_struct = self._parse(service.struct_parameter)
        # As upstream, duplicate key values collapse into one
        keys = {x['key_value']: {'long_name': x['long_name'], 'long_name_id': x['long_name_id']}
                for x in parsed_keys['keys']}
        rows = {x['long_name']: x for x in parsed_struct['table_rows']}
        result = []
        for did, key in keys.items():
            long_name = key['long_name']
            row = rows.get(long_name)
            # Some tables name the row with spaces where the key text has underscores (even MCD Kernel complains)
            if row is None:
                row = rows.get(long_name.replace('_', ' '))
            if row is None:
                raise RuntimeError('Failed to find table row for {}'.format(long_name))
            # parse_dop checked that the row's long name equals its map key
            result.append((table_key + (row['long_name'], did), _entry(did, long_name, key['long_name_id'], row)))
        return result

    def _whole_decimal_table(self, table_key, table):
        result = []
        for item in table['table_key_map']:
            row = self._row(item['reference'])
            did = int(item['map_key'])
            result.append((table_key + (item['map_key'], did), _entry(did, row['long_name'], row['long_name_id'], row)))
        return result

    def _referenced_row(self, table_key, table, family, service):
        row_short_name = service.key_parameter['row_reference_short_name']
        row_map = self.reader._row_map(table_key, table)
        if row_short_name not in row_map:
            raise RuntimeError('Table row {} of service {} not found'.format(row_short_name, service.short_name))
        map_key, row_reference = row_map[row_short_name]
        row = self._row(row_reference)
        if family == FAMILY_NAMES:
            scales = [key for key in self._keys(table_key, service.key_parameter) if key['long_name'] == map_key]
            if len(scales) != 1:
                raise RuntimeError('Expected one DID for table key {}, found {}'.format(map_key, len(scales)))
            did = scales[0]['key_value']
            long_name = scales[0]['long_name']
            long_name_id = scales[0]['long_name_id']
        else:
            did = int(map_key)
            long_name = row['long_name']
            long_name_id = row['long_name_id']
        return (table_key + (map_key, did), _entry(did, long_name, long_name_id, row))
