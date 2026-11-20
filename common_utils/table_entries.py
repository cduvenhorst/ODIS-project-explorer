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
