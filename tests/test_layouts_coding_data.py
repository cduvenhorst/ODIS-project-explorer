"""Layout tests for the coding data loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
Where a loader reads an object of any type, MCD_AUDIENCE stands in.
"""
import unittest

from tests import support
from tests.support import ObjectBytes
from tests.test_vw_layouts_services import parameter_body


def load(type_name, body):
    return support.load(type_name, body)


def odx_link_body(id_ref='ID1', doc_ref='DOC1', layer=False):
    return ObjectBytes().ascii(id_ref).ascii(doc_ref).flag(layer)


def odx_link(id_ref='ID1', doc_ref='DOC1', layer=False):
    return {'#OBJECT_TYPE': 'DB_ODX_LINK', 'id_ref': id_ref, 'doc_ref': doc_ref,
            'is_layer_doc_type': layer}


class OdxLinkTests(unittest.TestCase):
    def test_db_odx_link_minimal(self):
        self.assertEqual(load('DB_ODX_LINK', ObjectBytes().ascii(None).ascii(None).flag(False)),
                         {'#OBJECT_TYPE': 'DB_ODX_LINK', 'id_ref': None, 'doc_ref': None,
                          'is_layer_doc_type': False})

    def test_db_odx_link_all_branches(self):
        self.assertEqual(load('DB_ODX_LINK', odx_link_body(layer=True)), odx_link(layer=True))

    def test_db_odx_links_minimal(self):
        self.assertEqual(load('DB_ODX_LINKS', ObjectBytes().u32(0)), [])

    def test_db_odx_links_all_branches(self):
        body = ObjectBytes().u32(2).nested('DB_ODX_LINK', odx_link_body()).absent()
        self.assertEqual(load('DB_ODX_LINKS', body), [odx_link(), None])

    def test_mcd_db_parameter_dop_base_odx_link(self):
        body = parameter_body(reference=True, dop_base=odx_link_body(), dop_base_type='DB_ODX_LINK')
        self.assertEqual(load('MCD_DB_PARAMETER', body)['dop_base'], odx_link())
