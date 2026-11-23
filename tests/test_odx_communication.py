"""Tests for the ODX services, jobs, requests, responses and functional classes."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import communication
from odx_export.context import resolve_unpooled
from tests.odx_support import context

OWN = '0.0.0@L.sd'
OTHER = '0.0.0@M.sd'


def reference(object_id, pool_id=OWN, attributes=None):
    result = {'object_id': object_id, 'pool_id': pool_id}
    if attributes is not None:
        result['attributes'] = attributes
    return result


def named(object_reference, name='N'):
    return {'name': name, 'reference': object_reference}


def names(short_name, oid=None, **fields):
    result = {'short_name': short_name, 'long_name': None, 'long_name_id': None, 'description': None,
              'description_id': None, 'unique_object_id': oid}
    result.update(fields)
    return result


def audience(**flags):
    result = {'supplier': True, 'development': True, 'manufacturing': True, 'after_sales': True,
              'after_market': True}
    result.update(flags)
    return result


def primitive(short_name, oid=None, **fields):
    """Fields of MCD_DB_DIAG_COM_PRIMITIVE."""
    result = names(short_name, oid)
    result.update({'request_reference': None, 'positive_response_references': [],
                   'negative_response_references': [], 'functional_class_references': [], 'semantic': None,
                   'transmission_mode': 'eSEND_AND_RECEIVE', 'is_api_executable': True, 'is_no_operation': False,
                   'diagnostic_class': 0, 'ecu_state_transition_references': [], 'ecu_state_references': [],
                   'has_suppress_positive_response_capability': False,
                   'positive_response_suppress_bit_mask': None,
                   'has_positive_response_suppress_parameter_short_name_path': None,
                   'positive_response_suppress_parameter_short_name_path': None,
                   'positive_response_suppress_parameter_short_name': None})
    result.update(fields)
    return result


def data_primitive(short_name, oid=None, **fields):
    """Fields of MCD_DB_DATA_PRIMITIVE, which includes the DiagCom primitive."""
    result = primitive(short_name, oid)
    result.update({'access_level': None, 'audience_state': audience(), 'repetition_mode': 'eNOT_REPEATING',
                   'related_data_primitives': [], 'disabled_additional_audiences': [],
                   'enabled_additional_audiences': [], 'special_data_group_references': []})
    result.update(fields)
    return result


def service(short_name, oid=None, addressing_mode='ePHYSICAL', **fields):
    result = data_primitive(short_name, oid)
    result.update({'addressing_mode': addressing_mode, 'service_protocol_parameters': [],
                   'runtime_mode': 'eNONCYCLIC', 'is_multiple': False})
    result.update(fields)
    return result


def communication_primitive(short_name, **fields):
    """MCD_DB_STARTCOMMUNICATION or MCD_DB_STOPCOMMUNICATION: no addressing mode, no audience."""
    result = primitive(short_name)
    result['service_protocol_parameters'] = []
    result.update(fields)
    return result


def job(short_name, oid=None, **fields):
    result = data_primitive(short_name, oid)
    result.update({'major': 1, 'minor': 0, 'revision': 0, 'code_informations': None,
                   'is_reduced_result_enabled': False})
    result.update(fields)
    return result


def code_information(**fields):
    result = {'#OBJECT_TYPE': 'MCD_DB_CODE_INFORMATION', 'code_file': '', 'encryption': '', 'syntax': '',
              'revision': '', 'entry_point': '', 'library_references': []}
    result.update(fields)
    return result


def parameter(short_name='P1'):
    return {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_SIMPLE', 'description': None, 'long_name': None,
            'short_name': short_name, 'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            'bit_position': 0, 'byte_position': 0, 'default_value': None, 'semantic': None,
            'system_parameter': None, 'mcd_parameter_type': 'eVALUE', 'diag_coded_type': None,
            'dop_base_reference': None, 'is_byte_position_available': True,
            'special_data_group_references': []}


def request(short_name, oid=None, parameters=None):
    result = names(short_name, oid)
    result.update({'request_parameters': parameters if parameters is not None else [parameter()],
                   'special_data_group_references': []})
    return result


def response(short_name, response_type, oid=None, parameters=None):
    result = names(short_name, oid)
    result.update({'response_parameters': parameters if parameters is not None else [parameter()],
                   'response_type': response_type, 'special_data_group_references': []})
    return result


def functional_class(short_name, oid=None, **fields):
    result = names(short_name, oid, **fields)
    result['data_primitive_references'] = []
    return result


def layer_list(*keys):
    """A layer reference list (string-to-reference map) of own keys."""
    return [{'map_key': key, 'reference': reference(key)} for key in keys]


def tags(element):
    return [child.tag for child in element]


def diag_comms(ctx, layer_data=None):
    return communication.add_diag_comms(ctx, ET.Element('ECU-SHARED-DATA'), layer_data or {})


class DiagServiceTests(unittest.TestCase):
    def full_context(self):
        return context({
            'DC_L_S1': ('MCD_DB_SERVICE', service(
                'S1', oid='OID-S1', semantic='DATA', diagnostic_class=3, long_name='Service', long_name_id='TI_1',
                functional_class_references=[named(reference('FC_L_F1'))],
                audience_state=audience(development=False, after_market=False),
                related_data_primitives=[named(reference('DC_L_S2', attributes=['SUB-SERVICE', 'X']))],
                ecu_state_references=[named(reference('ST_L_C1.Default', attributes=['SEM']))],
                ecu_state_transition_references=[named(reference('STR_L_C1.T1', attributes=['SEM']))],
                request_reference=reference('REQ_L_Q1'),
                positive_response_references=[named(reference('RSP_L_P1'))],
                negative_response_references=[named(reference('RSP_L_N1')),
                                              named(reference('RSP_N_N2', '5.4.0@N.sd'))],
                has_suppress_positive_response_capability=True,
                positive_response_suppress_bit_mask=bytearray(b'\x80'),
                has_positive_response_suppress_parameter_short_name_path=False,
                positive_response_suppress_parameter_short_name='SubFunction')),
            'DC_L_S2': ('MCD_DB_SERVICE', service('S2', addressing_mode='eFUNCTIONAL')),
            'FC_L_F1': ('MCD_DB_FUNCTIONAL_CLASS', functional_class('F1')),
            'ST_L_C1.Default': ('MCD_DB_ECU_STATE', names('Default')),
            'STR_L_C1.T1': ('MCD_DB_ECU_STATE_TRANSITION', names('T1')),
            'REQ_L_Q1': ('MCD_DB_REQUEST', request('Q1')),
            'RSP_L_P1': ('MCD_DB_RESPONSE', response('P1', 'ePOSITIVE_RESPONSE')),
            'RSP_L_N1': ('MCD_DB_RESPONSE', response('N1', 'eLOCAL_NEG_RESPONSE')),
        }, object_type=lambda pool_id, object_id: 'MCD_DB_RESPONSE' if object_id == 'RSP_N_N2' else None)

    def test_diag_service_full(self):
        ctx = self.full_context()
        written = diag_comms(ctx, {'diag_com_primitive_references': layer_list('DC_L_S2', 'DC_L_S1')})
        self.assertEqual(written.tag, 'DIAG-COMMS')
        self.assertEqual([element.get('ID') for element in written], ['S2', 'S1'])
        element = written[1]
        self.assertEqual(element.tag, 'DIAG-SERVICE')
        self.assertEqual(dict(element.attrib), {'ID': 'S1', 'OID': 'OID-S1', 'SEMANTIC': 'DATA',
                                                'DIAGNOSTIC-CLASS': 'VARIANTIDENTIFICATION',
                                                'ADDRESSING': 'PHYSICAL'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'LONG-NAME', 'FUNCT-CLASS-REFS', 'AUDIENCE',
                                         'RELATED-DIAG-COMM-REFS', 'PRE-CONDITION-STATE-REFS',
                                         'STATE-TRANSITION-REFS', 'REQUEST-REF', 'POS-RESPONSE-REFS',
                                         'NEG-RESPONSE-REFS', 'POS-RESPONSE-SUPPRESSABLE'])
        self.assertEqual(element.find('FUNCT-CLASS-REFS/FUNCT-CLASS-REF').attrib, {'ID-REF': 'F1'})
        related = element.find('RELATED-DIAG-COMM-REFS/RELATED-DIAG-COMM-REF')
        self.assertEqual(related.get('ID-REF'), 'S2')
        self.assertEqual(related.findtext('RELATION-TYPE'), 'SUB-SERVICE')
        self.assertEqual(element.find('PRE-CONDITION-STATE-REFS/PRE-CONDITION-STATE-REF').attrib,
                         {'ID-REF': 'C1.Default'})
        self.assertEqual(element.find('STATE-TRANSITION-REFS/STATE-TRANSITION-REF').attrib, {'ID-REF': 'C1.T1'})
        self.assertEqual(element.find('REQUEST-REF').attrib, {'ID-REF': 'Q1'})
        self.assertEqual(element.find('POS-RESPONSE-REFS/POS-RESPONSE-REF').attrib, {'ID-REF': 'P1'})
        self.assertEqual([dict(ref.attrib) for ref in element.find('NEG-RESPONSE-REFS')],
                         [{'ID-REF': 'N1'}, {'ID-REF': 'N2', 'DOCREF': 'N', 'DOCTYPE': 'LAYER'}])
        suppressable = element.find('POS-RESPONSE-SUPPRESSABLE')
        self.assertEqual(tags(suppressable), ['BIT-MASK', 'VALUE-SNREF'])
        self.assertEqual(suppressable.findtext('BIT-MASK'), '80')
        self.assertEqual(suppressable.find('VALUE-SNREF').attrib, {'SHORT-NAME': 'SubFunction'})
        self.assertEqual(written[0].get('ADDRESSING'), 'FUNCTIONAL')
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'AUDIENCE'])
        self.assertEqual(ctx.report['empty_references'], 0)
        self.assertEqual(ctx.report['unresolvable_references'], 0)
        self.assertEqual(ctx.used, {'DC_L_S1', 'DC_L_S2'})

    def test_diag_service_audience_writes_only_false_flags(self):
        ctx = context({
            'DC_L_S1': ('MCD_DB_SERVICE', service('S1', audience_state=audience(
                supplier=False, manufacturing=False, after_sales=False))),
            'DC_L_S2': ('MCD_DB_SERVICE', service('S2')),
            'DC_L_S3': ('MCD_DB_SERVICE', service('S3', audience_state=None)),
        })
        written = diag_comms(ctx)
        self.assertEqual(dict(written[0].find('AUDIENCE').attrib),
                         {'IS-SUPPLIER': 'false', 'IS-MANUFACTURING': 'false', 'IS-AFTERSALES': 'false'})
        self.assertEqual(dict(written[1].find('AUDIENCE').attrib), {})
        self.assertIsNone(written[2].find('AUDIENCE'))

    def test_suppressable_with_short_name_path(self):
        ctx = context({'DC_L_S1': ('MCD_DB_SERVICE', service(
            'S1', has_suppress_positive_response_capability=True,
            positive_response_suppress_bit_mask=bytearray(b'\x7f\x00'),
            has_positive_response_suppress_parameter_short_name_path=True,
            positive_response_suppress_parameter_short_name_path='Struct.SubFunction'))})
        suppressable = diag_comms(ctx)[0].find('POS-RESPONSE-SUPPRESSABLE')
        self.assertEqual(suppressable.findtext('BIT-MASK'), '7F00')
        self.assertEqual(suppressable.find('VALUE-SNPATHREF').attrib, {'SHORT-NAME-PATH': 'Struct.SubFunction'})

    def test_unknown_addressing_mode_and_diagnostic_class(self):
        ctx = context({
            'DC_L_S1': ('MCD_DB_SERVICE', service('S1', addressing_mode='eUNDEFINED', diagnostic_class=1)),
            'DC_L_S2': ('MCD_DB_SERVICE', service('S2', addressing_mode='eFUNCTIONAL_OR_PHYSICAL',
                                                  diagnostic_class=2)),
        })
        written = diag_comms(ctx)
        self.assertIsNone(written[0].get('ADDRESSING'))
        self.assertEqual(written[0].get('DIAGNOSTIC-CLASS'), 'STARTCOMM')
        self.assertEqual(written[1].get('ADDRESSING'), 'FUNCTIONAL-OR-PHYSICAL')
        self.assertEqual(written[1].get('DIAGNOSTIC-CLASS'), 'STOPCOMM')

    def test_start_and_stop_communication_without_addressing(self):
        ctx = context({
            'DC_L_C1': ('MCD_DB_STARTCOMMUNICATION', communication_primitive(
                'StartComm', semantic='STARTCOMM', request_reference=reference('DC_L_Q1'),
                positive_response_references=[named(reference('DC_L_P1'))])),
            'DC_L_C2': ('MCD_DB_STOPCOMMUNICATION', communication_primitive('StopComm', semantic='STOPCOMM')),
            'DC_L_Q1': ('MCD_DB_REQUEST', request('Q1')),
            'DC_L_P1': ('MCD_DB_RESPONSE', response('P1', 'ePOSITIVE_RESPONSE')),
        })
        written = diag_comms(ctx)
        self.assertEqual([element.tag for element in written], ['DIAG-SERVICE', 'DIAG-SERVICE'])
        self.assertEqual(dict(written[0].attrib), {'ID': 'C1', 'SEMANTIC': 'STARTCOMM'})
        self.assertEqual(dict(written[1].attrib), {'ID': 'C2', 'SEMANTIC': 'STOPCOMM'})
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'REQUEST-REF', 'POS-RESPONSE-REFS'])
        self.assertEqual(written[0].find('REQUEST-REF').attrib, {'ID-REF': 'Q1'})
        self.assertEqual(tags(written[1]), ['SHORT-NAME'])
        self.assertEqual(ctx.used, {'DC_L_C1', 'DC_L_C2'})

    def test_service_with_empty_request_reference(self):
        ctx = context({
            'DC_L_S1': ('MCD_DB_SERVICE', service('S1', request_reference={'object_id': '', 'pool_id': ''})),
            'DC_L_S2': ('MCD_DB_SERVICE', service('S2', request_reference=None)),
        })
        written = diag_comms(ctx)
        self.assertIsNone(written[0].find('REQUEST-REF'))
        self.assertIsNone(written[1].find('REQUEST-REF'))
        # Only the present reference without object ID counts; the unset one is absent.
        self.assertEqual(ctx.report['empty_references'], 1)

    def test_empty_reference_lists_write_no_containers(self):
        ctx = context({'DC_L_S1': ('MCD_DB_SERVICE', service(
            'S1', positive_response_references=[named({'object_id': '', 'pool_id': OWN})],
            related_data_primitives=[named(reference('DC_L_S9', attributes=[]))]))})
        element = diag_comms(ctx)[0]
        self.assertIsNone(element.find('POS-RESPONSE-REFS'))
        self.assertEqual(element.find('RELATED-DIAG-COMM-REFS/RELATED-DIAG-COMM-REF').attrib, {'ID-REF': 'DC_L_S9'})
        self.assertIsNone(element.find('RELATED-DIAG-COMM-REFS/RELATED-DIAG-COMM-REF/RELATION-TYPE'))
        self.assertEqual(ctx.report['empty_references'], 1)
        self.assertEqual(ctx.report['unresolvable_references'], 1)

    def test_other_type_under_dc_prefix_stays_unused(self):
        ctx = context({
            'DC_L_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_L_M1': ('MCD_DB_MULTIPLE_ECU_JOB', {}),
        })
        written = diag_comms(ctx)
        self.assertEqual([element.get('ID') for element in written], ['S1'])
        self.assertEqual(ctx.unused(), {'MCD_DB_MULTIPLE_ECU_JOB': 1})

    def test_no_diag_comms(self):
        ctx = context({'DC_L_Q1': ('MCD_DB_REQUEST', request('Q1'))})
        parent = ET.Element('ECU-SHARED-DATA')
        self.assertIsNone(communication.add_diag_comms(ctx, parent, {}))
        self.assertEqual(len(parent), 0)


class SingleEcuJobTests(unittest.TestCase):
    def test_single_ecu_job_with_prog_codes(self):
        ctx = context({
            'DC_L_J1': ('MCD_DB_SINGLE_ECU_JOB', job(
                'J1', oid='OID-J1', semantic='FUNCTION', diagnostic_class=3,
                functional_class_references=[named(reference('FC_L_F1'))],
                audience_state=audience(supplier=False),
                related_data_primitives=[named(reference('DC_L_J2', attributes=['CALLS']))],
                ecu_state_references=[named(reference('ST_L_C1.Default'))],
                ecu_state_transition_references=[named(reference('STR_L_C1.T1'))],
                code_informations=[
                    code_information(code_file='job.jar', encryption='', syntax='JAR', revision='1.0',
                                     entry_point='Main', library_references=[
                                         {'map_key': 'LIB1', 'reference': {'object_id': 'LIB_L_1',
                                                                           'pool_id': None, 'object_id2': ''}}]),
                    None,
                    code_information(code_file='other.jar', syntax='JAR', revision='2')])),
            'DC_L_J2': ('MCD_DB_SINGLE_ECU_JOB', job('J2')),
            'FC_L_F1': ('MCD_DB_FUNCTIONAL_CLASS', functional_class('F1')),
            'ST_L_C1.Default': ('MCD_DB_ECU_STATE', names('Default')),
            'STR_L_C1.T1': ('MCD_DB_ECU_STATE_TRANSITION', names('T1')),
        })
        written = diag_comms(ctx)
        element = written[0]
        self.assertEqual(element.tag, 'SINGLE-ECU-JOB')
        self.assertEqual(dict(element.attrib), {'ID': 'J1', 'OID': 'OID-J1', 'SEMANTIC': 'FUNCTION'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'FUNCT-CLASS-REFS', 'AUDIENCE', 'RELATED-DIAG-COMM-REFS',
                                         'PRE-CONDITION-STATE-REFS', 'STATE-TRANSITION-REFS', 'PROG-CODES'])
        self.assertEqual(dict(element.find('AUDIENCE').attrib), {'IS-SUPPLIER': 'false'})
        self.assertEqual(element.findtext('RELATED-DIAG-COMM-REFS/RELATED-DIAG-COMM-REF/RELATION-TYPE'), 'CALLS')
        codes = element.find('PROG-CODES')
        self.assertEqual(tags(codes), ['PROG-CODE', 'PROG-CODE'])
        self.assertEqual(tags(codes[0]), ['CODE-FILE', 'SYNTAX', 'REVISION', 'ENTRYPOINT', 'LIBRARY-REFS'])
        self.assertEqual([codes[0].findtext(tag) for tag in ('CODE-FILE', 'SYNTAX', 'REVISION', 'ENTRYPOINT')],
                         ['job.jar', 'JAR', '1.0', 'Main'])
        self.assertEqual(codes[0].find('LIBRARY-REFS/LIBRARY-SNREF').attrib, {'SHORT-NAME': 'LIB_L_1'})
        self.assertEqual(tags(codes[1]), ['CODE-FILE', 'SYNTAX', 'REVISION'])
        self.assertEqual(tags(written[1]), ['SHORT-NAME', 'AUDIENCE'])
        self.assertEqual(ctx.used, {'DC_L_J1', 'DC_L_J2'})


class RequestResponseTests(unittest.TestCase):
    def test_requests_and_responses_under_dc_prefix(self):
        ctx = context({
            'DC_L_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_L_Q1': ('MCD_DB_REQUEST', request('Q1', oid='OID-Q1')),
            'REQ_L_Q2': ('MCD_DB_REQUEST', request('Q2')),
            'DC_L_P1': ('MCD_DB_RESPONSE', response('P1', 'ePOSITIVE_RESPONSE', oid='OID-P1')),
            'RSP_L_P2': ('MCD_DB_RESPONSE', response('P2', 'ePOSITIVE_RESPONSE')),
            'RSP_L_N1': ('MCD_DB_RESPONSE', response('N1', 'eLOCAL_NEG_RESPONSE')),
        })
        esd = ET.Element('ECU-SHARED-DATA')
        comms = communication.add_diag_comms(ctx, esd, {})
        requests = communication.add_requests(ctx, esd, {})
        self.assertIsNone(communication.add_responses(ctx, esd, {}))
        self.assertEqual([element.get('ID') for element in comms], ['S1'])
        self.assertEqual(tags(esd), ['DIAG-COMMS', 'REQUESTS', 'POS-RESPONSES', 'NEG-RESPONSES'])
        self.assertEqual([dict(element.attrib) for element in requests], [{'ID': 'Q1', 'OID': 'OID-Q1'}, {'ID': 'Q2'}])
        self.assertEqual(tags(requests[0]), ['SHORT-NAME', 'PARAMS'])
        self.assertEqual(requests[0].findtext('PARAMS/PARAM/SHORT-NAME'), 'P1')
        positives = esd.find('POS-RESPONSES')
        self.assertEqual([(element.tag, element.get('ID')) for element in positives],
                         [('POS-RESPONSE', 'P1'), ('POS-RESPONSE', 'P2')])
        self.assertEqual(positives[0].get('OID'), 'OID-P1')
        self.assertEqual(tags(positives[0]), ['SHORT-NAME', 'PARAMS'])
        self.assertEqual([(element.tag, element.get('ID')) for element in esd.find('NEG-RESPONSES')],
                         [('NEG-RESPONSE', 'N1')])
        self.assertEqual(ctx.unused(), {})

    def test_requests_follow_layer_order(self):
        ctx = context({
            'REQ_L_Q1': ('MCD_DB_REQUEST', request('Q1')),
            'DC_L_Q2': ('MCD_DB_REQUEST', request('Q2')),
            'REQ_L_Q3': ('MCD_DB_REQUEST', request('Q3', parameters=[])),
        })
        requests = communication.add_requests(ctx, ET.Element('ECU-SHARED-DATA'),
                                              {'request_references': layer_list('REQ_L_Q3')})
        self.assertEqual([element.get('ID') for element in requests], ['Q3', 'Q1', 'Q2'])
        self.assertEqual(tags(requests[0]), ['SHORT-NAME'])

    def test_global_negative_responses_follow_layer_order(self):
        ctx = context({
            'RSP_L_G1': ('MCD_DB_RESPONSE', response('G1', 'eGLOBAL_NEG_RESPONSE')),
            'RSP_L_G2': ('MCD_DB_RESPONSE', response('G2', 'eGLOBAL_NEG_RESPONSE')),
            'DC_L_G3': ('MCD_DB_RESPONSE', response('G3', 'eGLOBAL_NEG_RESPONSE')),
            'RSP_L_N1': ('MCD_DB_RESPONSE', response('N1', 'eLOCAL_NEG_RESPONSE')),
        })
        esd = ET.Element('ECU-SHARED-DATA')
        communication.add_responses(ctx, esd,
                                    {'global_negative_response_references': layer_list('DC_L_G3', 'RSP_L_G2')})
        self.assertEqual(tags(esd), ['NEG-RESPONSES', 'GLOBAL-NEG-RESPONSES'])
        self.assertEqual([(element.tag, element.get('ID')) for element in esd.find('GLOBAL-NEG-RESPONSES')],
                         [('GLOBAL-NEG-RESPONSE', 'G3'), ('GLOBAL-NEG-RESPONSE', 'G2'),
                          ('GLOBAL-NEG-RESPONSE', 'G1')])

    def test_unknown_response_type_stays_unused(self):
        ctx = context({'RSP_L_X1': ('MCD_DB_RESPONSE', response('X1', 0x6F09))})
        esd = ET.Element('ECU-SHARED-DATA')
        communication.add_responses(ctx, esd, {})
        self.assertEqual(len(esd), 0)
        self.assertEqual(ctx.unused(), {'MCD_DB_RESPONSE': 1})

    def test_no_requests(self):
        parent = ET.Element('ECU-SHARED-DATA')
        self.assertIsNone(communication.add_requests(context({}), parent, {}))
        self.assertEqual(len(parent), 0)


class FunctClassTests(unittest.TestCase):
    def test_funct_classes(self):
        ctx = context({
            'FC_L_F1': ('MCD_DB_FUNCTIONAL_CLASS', functional_class('F1', oid='OID-F1', long_name='Class',
                                                                    long_name_id='TI_1')),
            'FC_L_F2': ('MCD_DB_FUNCTIONAL_CLASS', functional_class('F2', description='<p>Text</p>')),
        })
        written = communication.add_funct_classes(ctx, ET.Element('ECU-SHARED-DATA'),
                                                  {'functional_class_references': layer_list('FC_L_F2')})
        self.assertEqual(written.tag, 'FUNCT-CLASSS')
        self.assertEqual([dict(element.attrib) for element in written], [{'ID': 'F2'}, {'ID': 'F1', 'OID': 'OID-F1'}])
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'DESC'])
        self.assertEqual(tags(written[1]), ['SHORT-NAME', 'LONG-NAME'])
        self.assertEqual(written[1].find('LONG-NAME').get('TI'), 'TI_1')
        self.assertEqual(ctx.used, {'FC_L_F1', 'FC_L_F2'})

    def test_no_funct_classes(self):
        parent = ET.Element('ECU-SHARED-DATA')
        self.assertIsNone(communication.add_funct_classes(context({}), parent, {}))
        self.assertEqual(len(parent), 0)



LAYER_POOL = '0.0.0@B.bv'
VARIANT_POOL = '0.0.0@E.ev'


def layer_view(objects, layer='V1', **kwargs):
    """View of variant V1 of pool B, which holds the base variant B and the variants V1 and V2."""
    return context(objects, pool_id=LAYER_POOL, pool_layers=['B', 'V1', 'V2'], **kwargs).for_layer(layer)


def layer_diag_comms(ctx, entries):
    return communication.add_diag_comms(ctx, ET.Element('ECU-VARIANT'), {'diag_com_primitive_references': entries})


def summary(element):
    return [(child.tag, dict(child.attrib)) for child in element]


class LayerDiagCommTests(unittest.TestCase):
    def test_listed_sister_service_becomes_diag_comm_ref_in_list_position(self):
        ctx = layer_view({
            'DC_V1_S0': ('MCD_DB_SERVICE', service('S0')),
            'DC_V1_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_V2_S2': ('MCD_DB_SERVICE', service('S2')),
            'DC_V1_S3': ('MCD_DB_SERVICE', service('S3')),
        })
        written = layer_diag_comms(ctx, [{'map_key': 'S1', 'reference': reference('DC_V1_S1', LAYER_POOL)},
                                         {'map_key': 'S2', 'reference': reference('DC_V2_S2', LAYER_POOL)},
                                         {'map_key': 'S3', 'reference': reference('DC_V1_S3', LAYER_POOL)}])
        self.assertEqual(summary(written), [
            ('DIAG-SERVICE', {'ID': 'S1', 'ADDRESSING': 'PHYSICAL'}),
            ('DIAG-COMM-REF', {'ID-REF': 'S2', 'DOCREF': 'V2', 'DOCTYPE': 'LAYER'}),
            ('DIAG-SERVICE', {'ID': 'S3', 'ADDRESSING': 'PHYSICAL'}),
            ('DIAG-SERVICE', {'ID': 'S0', 'ADDRESSING': 'PHYSICAL'})])
        self.assertEqual(ctx.used, {'DC_V1_S0', 'DC_V1_S1', 'DC_V1_S3'})
        self.assertEqual(ctx.report['unresolvable_references'], 0)

    def test_service_of_shared_data_pool_becomes_diag_comm_ref(self):
        ctx = layer_view({'DC_V1_S1': ('MCD_DB_SERVICE', service('S1'))},
                         object_type=lambda pool_id, object_id: 'MCD_DB_SERVICE')
        written = layer_diag_comms(ctx, [named(reference('DC_S_X', '0.0.0@S.sd')),
                                         named(reference('DC_V1_S1', LAYER_POOL))])
        self.assertEqual(summary(written), [
            ('DIAG-COMM-REF', {'ID-REF': 'X', 'DOCREF': 'S', 'DOCTYPE': 'LAYER'}),
            ('DIAG-SERVICE', {'ID': 'S1', 'ADDRESSING': 'PHYSICAL'})])
        self.assertEqual(ctx.report['unresolvable_references'], 0)

    def test_own_service_is_written_once_in_full(self):
        ctx = layer_view({
            'DC_V1_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_V1_S2': ('MCD_DB_SERVICE', service('S2')),
            'DC_V2_S3': ('MCD_DB_SERVICE', service('S3')),
        })
        written = layer_diag_comms(ctx, [named(reference('DC_V1_S2', LAYER_POOL)), reference('DC_V1_S2', LAYER_POOL),
                                         named(reference('DC_V2_S3', LAYER_POOL)),
                                         named(reference('DC_V2_S3', LAYER_POOL))])
        self.assertEqual([(element.tag, element.get('ID') or element.get('ID-REF')) for element in written],
                         [('DIAG-SERVICE', 'S2'), ('DIAG-COMM-REF', 'S3'), ('DIAG-SERVICE', 'S1')])

    def test_flash_job_is_written_as_single_ecu_job(self):
        ctx = layer_view({'DC_V1_F1': ('MCD_DB_FLASH_JOB', job(
            'F1', oid='OID-F1', code_informations=[code_information(code_file='flash.jar', syntax='JAR')]))})
        written = layer_diag_comms(ctx, [])
        self.assertEqual(summary(written), [('SINGLE-ECU-JOB', {'ID': 'F1', 'OID': 'OID-F1'})])
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'AUDIENCE', 'PROG-CODES'])
        self.assertEqual(written[0].findtext('PROG-CODES/PROG-CODE/CODE-FILE'), 'flash.jar')
        self.assertEqual(ctx.used, {'DC_V1_F1'})

    def test_shared_data_pool_keeps_its_diag_comms(self):
        ctx = context({
            'DC_L_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_L_F1': ('MCD_DB_FLASH_JOB', job('F1')),
        })
        written = diag_comms(ctx, {'diag_com_primitive_references': [named(reference('DC_M_S9', OTHER))]})
        self.assertEqual([element.get('ID') for element in written], ['S1'])
        self.assertEqual(ctx.unused(), {'MCD_DB_FLASH_JOB': 1})

    def test_reference_in_own_layer_to_other_type_is_reported(self):
        ctx = layer_view({
            'DC_V1_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_V1_Q1': ('MCD_DB_REQUEST', request('Q1')),
        })
        written = layer_diag_comms(ctx, [named(reference('DC_V1_Q1', LAYER_POOL)), named({'object_id': 'DC_V1_X',
                                                                                         'pool_id': None})])
        self.assertEqual([element.get('ID') for element in written], ['S1'])
        self.assertEqual(ctx.report['diag_comm_reference_not_written'], 2)


class UnpooledReferenceTests(unittest.TestCase):
    def test_unpooled_reference_to_own_object_is_own(self):
        ctx = context({
            'DC_E_S1': ('MCD_DB_SERVICE', service('S1')),
            'DC_E_S2': ('MCD_DB_SERVICE', service('S2')),
        }, pool_id=VARIANT_POOL)
        unpooled = {'object_id': 'DC_E_S2', 'pool_id': None}
        self.assertEqual(resolve_unpooled(ctx, unpooled), {'object_id': 'DC_E_S2', 'pool_id': VARIANT_POOL})
        self.assertEqual(ctx.ordered([named(unpooled)], ['DC_E_S1', 'DC_E_S2']), ['DC_E_S2', 'DC_E_S1'])
        written = layer_diag_comms(ctx, [named(unpooled)])
        self.assertEqual(summary(written), [('DIAG-SERVICE', {'ID': 'S2', 'ADDRESSING': 'PHYSICAL'}),
                                            ('DIAG-SERVICE', {'ID': 'S1', 'ADDRESSING': 'PHYSICAL'})])
        self.assertEqual(ctx.report['unpooled_reference_not_in_pool'], 0)

    def test_unpooled_reference_outside_pool_is_reported(self):
        ctx = context({'DC_E_S1': ('MCD_DB_SERVICE', service('S1'))}, pool_id=VARIANT_POOL)
        unpooled = {'object_id': 'DC_X_S9', 'pool_id': None}
        self.assertEqual(resolve_unpooled(ctx, unpooled), unpooled)
        self.assertEqual(ctx.report['unpooled_reference_not_in_pool'], 1)
        written = layer_diag_comms(ctx, [named(unpooled)])
        self.assertEqual([element.get('ID') for element in written], ['S1'])
        self.assertEqual(ctx.report['unpooled_reference_not_in_pool'], 2)

    def test_unpooled_reference_outside_variant_pools_is_unchanged(self):
        ctx = context({'DC_L_S1': ('MCD_DB_SERVICE', service('S1'))})
        unpooled = {'object_id': 'DC_L_S1', 'pool_id': None}
        self.assertEqual(resolve_unpooled(ctx, unpooled), unpooled)
        self.assertEqual(ctx.ordered([named(unpooled)], ['DC_L_S1']), ['DC_L_S1'])
        self.assertEqual(ctx.report['unpooled_reference_not_in_pool'], 0)


def longer_name_view(objects):
    """View of the base variant B of a pool whose variant B_V1 has a name that starts with B."""
    return context(objects, pool_id=LAYER_POOL, pool_layers=['B', 'B_V1']).for_layer('B')


class LongerLayerNameTests(unittest.TestCase):
    def test_own_keys_skip_keys_of_a_longer_layer_name(self):
        ctx = longer_name_view({
            'REQ_B_R1': ('MCD_DB_REQUEST', request('R1')),
            'REQ_B_V1_R1': ('MCD_DB_REQUEST', request('R1')),
            'DC_B_V1_R2': ('MCD_DB_REQUEST', request('R2')),
        })
        written = communication.add_requests(ctx, ET.Element('BASE-VARIANT'), {})
        self.assertEqual([element.get('ID') for element in written], ['R1'])
        self.assertEqual(ctx.used, {'REQ_B_R1'})

    def test_own_responses_skip_keys_of_a_longer_layer_name(self):
        ctx = longer_name_view({
            'RSP_B_P1': ('MCD_DB_RESPONSE', response('P1', 'ePOSITIVE_RESPONSE')),
            'RSP_B_V1_P1': ('MCD_DB_RESPONSE', response('P1', 'ePOSITIVE_RESPONSE')),
            'DC_B_V1_N1': ('MCD_DB_RESPONSE', response('N1', 'eLOCAL_NEG_RESPONSE')),
        })
        parent = ET.Element('BASE-VARIANT')
        communication.add_responses(ctx, parent, {})
        self.assertEqual(tags(parent), ['POS-RESPONSES'])
        self.assertEqual([element.get('ID') for element in parent.find('POS-RESPONSES')], ['P1'])
        self.assertEqual(ctx.used, {'RSP_B_P1'})


if __name__ == '__main__':
    unittest.main()
