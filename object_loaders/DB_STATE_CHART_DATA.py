from classes import DbObject
from common_utils import common_loaders


# Field names are the kernel setter names; per the getters, the keys are short names of a
# state transition (actions map) and of a state (precondition definitions map)
def load_map(stream):
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    entries = []
    positions = {}
    for _ in range(stream.loadNumericType(2)):
        key = stream.loadAsciiString()
        entry = {'map_key': key[0]}
        entry['items'] = [DbObject.load_object_from_stream_if_exists(stream) for _ in range(stream.loadNumericType(2))]
        common_loaders.put_map_entry(entries, positions, common_loaders.kernel_string_key(key), entry)
    return entries


def load(stream):
    obj = {}
    
    obj['state_transition_transition_actions_map'] = load_map(stream)
    obj['state_precondition_definitions_map'] = load_map(stream)
    
    # Precondition definitions without a DiagCom reference take their table parameter from
    # named stream C, one reference each in reading order
    # kernel: fails when either map holds an object of another type; kept readable for VW projects
    pending = [definition for entry in obj['state_precondition_definitions_map'] for definition in entry['items']
               if isinstance(definition, dict)
               and definition.get('#OBJECT_TYPE') == 'MCD_DB_PRECONDITION_DEFINITION'
               and definition['diag_com_primitive'] is None]
    readers = {}
    if pending:
        readers['C'] = lambda s: [common_loaders.load_reference(s, True) for _ in range(len(pending))]
    streams = common_loaders.loadNamedStreams(stream, readers)
    if pending:
        if 'C' not in streams:
            raise RuntimeError('Named stream C missing for {} precondition definitions'.format(len(pending)))
        for definition, reference in zip(pending, streams['C']):
            definition['table_parameter'] = reference
    
    return obj
